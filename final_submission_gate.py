#!/usr/bin/env python3
"""Fail-closed final submission gate for VÉRTICE / Agents for Humans."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    owner: str = "engineering"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> tuple[dict[str, Any] | None, bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
        return (value if isinstance(value, dict) else None), raw
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, b""


def get(data: dict[str, Any] | None, dotted: str, default: Any = None) -> Any:
    node: Any = data or {}
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def https_url(value: Any, hosts: set[str] | None = None) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and (hosts is None or parsed.hostname in hosts)


def evaluate(manifest: dict[str, Any], stage: str, paths: dict[str, Path]) -> dict[str, Any]:
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str, owner: str = "engineering") -> None:
        checks.append(Check(name, "PASS" if ok else "FAIL", detail, owner))

    loaded: dict[str, dict[str, Any] | None] = {}
    raw: dict[str, bytes] = {}
    for name in ("dossier", "application", "release", "demo", "compliance"):
        loaded[name], raw[name] = load(paths[name])
        add(f"{name}_json", loaded[name] is not None, f"{name} artifact is readable JSON")
    try:
        candidate_raw = paths["candidate"].read_bytes()
    except OSError:
        candidate_raw = b""
    add("candidate_bytes", bool(candidate_raw), "candidate archive exists and is nonempty")

    commit = str(get(manifest, "source.commit_sha", ""))
    candidate_sha = sha256(candidate_raw) if candidate_raw else ""
    app_sha = sha256(raw["application"]) if raw["application"] else ""
    add("manifest_schema", get(manifest, "schema") == "vertice.final-submission-manifest.v1", "final manifest schema")
    add("commit_format", bool(COMMIT_RE.fullmatch(commit)), "exact 40-character commit recorded")
    add("candidate_hash", get(manifest, "artifacts.candidate_sha256") == candidate_sha and bool(SHA_RE.fullmatch(candidate_sha)), "candidate bytes match manifest")
    for name in ("dossier", "application", "release", "demo", "compliance"):
        actual = sha256(raw[name]) if raw[name] else ""
        add(f"{name}_hash", get(manifest, f"artifacts.{name}_sha256") == actual and bool(SHA_RE.fullmatch(actual)), f"{name} bytes match manifest")

    add("dossier_schema", get(loaded["dossier"], "schema") == "vertice.release-evidence.v2", "release dossier v2")
    add("dossier_commit", get(loaded["dossier"], "build.commit_sha") == commit and bool(commit), "dossier commit matches manifest")
    add("dossier_candidate", get(loaded["dossier"], "build.candidate_sha256") == candidate_sha and bool(candidate_sha), "dossier candidate matches exact bytes")
    add("dossier_application", get(loaded["dossier"], "runtime.evidence_file_sha256") == app_sha and bool(app_sha), "dossier binds application evidence")

    add("application_schema", get(loaded["application"], "schema") == "vertice.application-e2e.v1", "application evidence schema")
    add("application_scope", get(loaded["application"], "scope") == "APPLICATION_E2E", "application evidence scope")
    add("application_pass", get(loaded["application"], "status") == "PASS" and get(loaded["application"], "checks_passed") == get(loaded["application"], "checks_total") and get(loaded["application"], "checks_total", 0) >= 17, "application checks all pass")
    add("application_runtime", get(loaded["application"], "runtime") == "REAL_STRANDS", "runtime is REAL_STRANDS")
    add("application_effect_truth", get(loaded["application"], "external_effect") == "SIMULATED", "external effect is truthfully SIMULATED")
    add("application_commit", get(loaded["application"], "source.commit_sha") == commit and bool(commit), "application evidence commit matches")

    add("release_schema", get(loaded["release"], "schema") == "vertice.release-gate.v2", "release gate schema")
    add("release_green", get(loaded["release"], "status") == "GREEN" and get(loaded["release"], "summary.failed") == 0, "release gate is GREEN")
    add("demo_schema", get(loaded["demo"], "schema") == "vertice.demo-freeze-gate.v1", "demo freeze gate schema")
    add("demo_green", get(loaded["demo"], "status") == "GREEN" and get(loaded["demo"], "summary.failed") == 0 and get(loaded["demo"], "summary.checks", 0) >= 39, "demo freeze gate is GREEN")
    add("compliance_schema", get(loaded["compliance"], "schema") == "vertice.submission-compliance-gate.v1", "submission compliance schema")
    add("compliance_green", get(loaded["compliance"], "status") == "GREEN" and get(loaded["compliance"], "summary.failed") == 0 and get(loaded["compliance"], "summary.checks", 0) >= 38, "submission compliance is GREEN")

    if stage in {"publication", "submission"}:
        repo = get(manifest, "public.repository_url")
        video = get(manifest, "public.video_url")
        add("repository_url", https_url(repo, {"github.com"}), "public GitHub repository URL recorded", "Manuel")
        add("video_url", https_url(video, {"youtube.com", "www.youtube.com", "youtu.be", "vimeo.com", "www.vimeo.com"}), "supported public video URL recorded", "Manuel")
        add("repository_access", get(manifest, "public.repository_http_status") == 200, "repository returned HTTP 200", "Manuel")
        add("video_access", get(manifest, "public.video_http_status") == 200, "video returned HTTP 200", "Manuel")
        add("access_timestamp", bool(get(manifest, "public.checked_at_utc")), "public access check timestamp recorded", "Manuel")

    if stage == "submission":
        add("builder_id", get(manifest, "manual.aws_builder_id_confirmed") is True, "AWS Builder ID confirmed", "Manuel")
        add("devpost_story", get(manifest, "manual.devpost_story_complete") is True, "Devpost story complete", "Manuel")
        add("devpost_media", get(manifest, "manual.devpost_media_complete") is True, "Devpost media complete", "Manuel")
        add("devpost_links", get(manifest, "manual.devpost_links_match") is True, "Devpost links match public artifacts", "Manuel")
        add("authorized_commit", get(manifest, "authorization.commit_sha") == commit and bool(commit), "authorization binds exact commit", "Manuel")
        add("authorized_candidate", get(manifest, "authorization.candidate_sha256") == candidate_sha and bool(candidate_sha), "authorization binds exact candidate", "Manuel")
        add("manual_authorization", get(manifest, "authorization.decision") == "MANUEL_AUTHORIZED_SUBMISSION", "explicit final authorization recorded", "Manuel")

    failed = [item for item in checks if item.status == "FAIL"]
    return {
        "schema": "vertice.final-submission-gate.v1",
        "stage": stage,
        "status": "GREEN" if not failed else "RED",
        "summary": {"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
        "manual_blockers": [item.name for item in failed if item.owner == "Manuel"],
        "checks": [asdict(item) for item in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--stage", choices=("candidate", "publication", "submission"), default="candidate")
    for name in ("candidate", "dossier", "application", "release", "demo", "compliance"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("final-submission-result.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    paths = {name: getattr(args, name) for name in ("candidate", "dossier", "application", "release", "demo", "compliance")}
    result = evaluate(manifest, args.stage, paths)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
