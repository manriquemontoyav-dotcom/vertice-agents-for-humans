#!/usr/bin/env python3
"""Black-box application E2E certifier for VÉRTICE / Agents for Humans.

It observes one HTTP server and emits application-scoped evidence only when all
required runtime invariants pass. External effects must remain simulated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SDK_VERSION = "1.54.0"
SDK_WHEEL_SHA256 = "ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Observation:
    status: int
    body: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_value(data: Any, names: tuple[str, ...]) -> Any:
    """Find the first named field in deterministic breadth-first order."""
    queue = [data]
    while queue:
        node = queue.pop(0)
        if isinstance(node, dict):
            for name in names:
                if name in node:
                    return node[name]
            queue.extend(node.values())
        elif isinstance(node, list):
            queue.extend(node)
    return None


def as_upper(value: Any) -> str:
    return str(value or "").strip().upper()


class HttpDriver:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(self, path: str, payload: dict[str, Any] | None = None) -> Observation:
        encoded=json.dumps(payload or {}, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=encoded,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = exc.code
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"{path} returned non-JSON response with HTTP {status}") from exc
        if not isinstance(body, dict):
            raise RuntimeError(f"{path} returned a non-object JSON response")
        return Observation(status=status, body=body)


def check(name: str, condition: bool, details: str = "") -> dict[str, str]:
    return {"name": name, "status": "PASS" if condition else "FAIL", "details": details}


def state_of(body: dict[str, Any]) -> str:
    return as_upper(find_value(body, ("state", "session_state", "runtime_state")))


def effect_count_of(body: dict[str, Any]) -> int | None:
    value = find_value(body, ("effect_count", "effects_count"))
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def receipt_of(body: dict[str, Any]) -> str:
    return str(find_value(body, ("execution_receipt", "receipt_id", "receipt")) or "")


def canonical_action_hash(action: dict[str, Any]) -> str:
    encoded = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def run_certification(
    driver: HttpDriver,
    commit_sha: str,
    source_archive: Path,
    sdk_wheel: Path,
    certifier_path: Path,
) -> dict[str, Any]:
    if not COMMIT_RE.fullmatch(commit_sha):
        raise ValueError("commit SHA must contain exactly 40 lowercase hexadecimal characters")

    source_sha = sha256_file(source_archive)
    wheel_sha = sha256_file(sdk_wheel)
    certifier_sha = sha256_file(certifier_path)
    if wheel_sha != SDK_WHEEL_SHA256:
        raise ValueError("Strands wheel SHA-256 does not match the pinned official artifact")
    checks: list[dict[str, str]] = []

    driver.post("/api/runtime/reset")
    started = driver.post("/api/runtime/start")
    runtime = as_upper(find_value(started.body, ("runtime", "agent_runtime", "runtime_classification")))
    interrupt_id = str(find_value(started.body, ("interrupt_id", "interruptId")) or "")
    tool_use_id = str(find_value(started.body, ("toolUseId", "tool_use_id")) or "")
    action_hash = str(find_value(started.body, ("exact_action_hash", "action_hash", "frozen_action_hash", "fingerprint")) or "")
    frozen_action = find_value(started.body, ("frozen_action", "exact_action", "action"))
    start_effects = effect_count_of(started.body)

    checks.extend([
        check("start_http_success", 200 <= started.status < 300, str(started.status)),
        check("real_strands_runtime", runtime == "REAL_STRANDS", runtime),
        check("confirm_interrupt", state_of(started.body) == "INTERRUPTED", state_of(started.body)),
        check("interrupt_id_present", bool(interrupt_id), interrupt_id),
        check("tool_use_id_present", bool(tool_use_id), tool_use_id),
        check("exact_action_frozen", frozen_action == {"proposal_id": "AFH-DEMO-001", "amount": 8750}),
        check("action_hash_present", bool(action_hash), action_hash),
        check("zero_effect_before_resolution", start_effects == 0, str(start_effects)),
    ])

    approved = driver.post("/api/runtime/approve-resume", {"interrupt_id": interrupt_id})
    approved_hash = str(find_value(approved.body, ("exact_action_hash", "action_hash", "frozen_action_hash", "fingerprint")) or "")
    approved_receipt = receipt_of(approved.body)
    approved_effects = effect_count_of(approved.body)
    checks.extend([
        check("approve_http_success", 200 <= approved.status < 300, str(approved.status)),
        check("approve_committed", state_of(approved.body) == "COMMITTED", state_of(approved.body)),
        check("action_hash_preserved", bool(action_hash) and approved_hash == action_hash, approved_hash),
        check("exactly_one_effect", approved_effects == 1, str(approved_effects)),
        check("execution_receipt_present", bool(approved_receipt), approved_receipt),
    ])

    replayed = driver.post("/api/runtime/replay")
    replay_receipt = receipt_of(replayed.body)
    replay_effects = effect_count_of(replayed.body)
    checks.append(check(
        "replay_same_receipt_no_second_effect",
        bool(approved_receipt) and replay_receipt == approved_receipt and replay_effects == 1,
        f"receipt={replay_receipt};effect_count={replay_effects}",
    ))

    driver.post("/api/runtime/reset")
    denied_start = driver.post("/api/runtime/start")
    denied_interrupt = str(find_value(denied_start.body, ("interrupt_id", "interruptId")) or "")
    denied = driver.post("/api/runtime/deny-resume", {"interrupt_id": denied_interrupt})
    denied_effects = effect_count_of(denied.body)
    checks.append(check(
        "deny_zero_effect",
        state_of(denied_start.body) == "INTERRUPTED" and denied_effects == 0,
        f"state={state_of(denied.body)};effect_count={denied_effects}",
    ))

    driver.post("/api/runtime/reset")
    tamper_start = driver.post("/api/runtime/start")
    tamper_interrupt = str(find_value(tamper_start.body, ("interrupt_id", "interruptId")) or "")
    tamper_approved = driver.post("/api/runtime/approve-resume", {"interrupt_id": tamper_interrupt})
    tampered = driver.post("/api/runtime/tamper")
    tamper_result = str(find_value(tampered.body, ("tamper_result", "mutation_result")) or "")
    tamper_blocked = "BLOCKED_8751" in tamper_result
    tamper_effects = effect_count_of(tampered.body)
    checks.extend([
        check("tamper_8751_blocked", state_of(tamper_start.body) == "INTERRUPTED" and state_of(tamper_approved.body) == "COMMITTED" and tamper_blocked, tamper_result),
        check("tamper_no_second_effect", tamper_effects == 1, str(tamper_effects)),
    ])

    passed = sum(item["status"] == "PASS" for item in checks)
    return {
        "schema": "vertice.application-e2e.v1",
        "scope": "APPLICATION_E2E",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "checks_passed": passed,
        "checks_total": len(checks),
        "source": {"commit_sha": commit_sha, "archive_sha256": source_sha},
        "certifier_sha256": certifier_sha,
        "sdk": {"version": SDK_VERSION, "wheel_sha256": wheel_sha},
        "runtime": "REAL_STRANDS" if runtime == "REAL_STRANDS" else runtime,
        "human_resolution": "CLIENT_RESOLUTION_UNVERIFIED_ACTOR",
        "external_effect": "SIMULATED",
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--sdk-wheel", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    certifier_path = Path(__file__).resolve()
    try:
        result = run_certification(
            HttpDriver(args.base_url, args.timeout),
            args.commit_sha,
            args.source_archive,
            args.sdk_wheel,
            certifier_path,
        )
    except Exception as exc:
        print(f"APPLICATION_E2E_CERTIFICATION_ERROR: {exc}", file=sys.stderr)
        return 2

    args.evidence.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "checks_passed", "checks_total", "scope", "runtime", "external_effect")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
