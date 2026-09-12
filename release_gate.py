#!/usr/bin/env python3
"""Evidence and provenance release gate for VÉRTICE / Agents for Humans."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SDK_VERSION = "1.54.0"
EXPECTED_SDK_WHEEL_SHA256 = "ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c"
EXPECTED_APP_EVIDENCE_SCHEMA = "vertice.application-e2e.v1"
EXPECTED_APP_SCOPE = "APPLICATION_E2E"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    owner: str


def get(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def parse_runtime_artifact(raw: bytes | None) -> tuple[dict[str, Any] | None, str]:
    if raw is None:
        return None, ""
    digest = hashlib.sha256(raw).hexdigest()
    try:
        artifact = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, digest
    return artifact if isinstance(artifact, dict) else None, digest


def evaluate(data: dict[str, Any], stage: str, runtime_artifact: bytes | None = None) -> dict[str, Any]:
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str, owner: str = "engineering") -> None:
        checks.append(Check(name, "PASS" if ok else "FAIL", detail, owner))

    commit = str(get(data, "build.commit_sha", ""))
    source_archive_sha = str(get(data, "build.source_archive_sha256", ""))
    candidate_sha = str(get(data, "build.candidate_sha256", ""))
    workflow_run_id = str(get(data, "build.workflow_run_id", ""))
    declared_artifact_sha = str(get(data, "runtime.evidence_file_sha256", ""))
    artifact, actual_artifact_sha = parse_runtime_artifact(runtime_artifact)

    add("dossier_schema", get(data, "schema") == "vertice.release-evidence.v2", "release dossier schema is v2")
    add("commit_sha", bool(COMMIT_RE.fullmatch(commit)), "exact 40-character commit SHA recorded")
    add("source_archive_sha256", bool(SHA256_RE.fullmatch(source_archive_sha)), "source archive SHA-256 recorded")
    add("candidate_sha256", bool(SHA256_RE.fullmatch(candidate_sha)), "candidate SHA-256 recorded")
    add("workflow_run_id", bool(workflow_run_id.strip()), "workflow run identifier recorded")
    add("clean_install", get(data, "build.clean_install") is True, "clean installation passed")
    add("regression", get(data, "tests.failures") == 0 and get(data, "tests.passed", 0) > 0, "automated regression has tests and zero failures")
    add("publication_scan_before", get(data, "security.scan_before") == "PASS", "pre-test safety scan passed")
    add("publication_scan_after", get(data, "security.scan_after") == "PASS", "post-test safety scan passed")
    add("secrets", get(data, "security.secret_findings") == 0, "zero secret findings")

    add("runtime_evidence_supplied", runtime_artifact is not None, "runtime evidence file supplied to gate")
    add("runtime_evidence_json", artifact is not None, "runtime evidence is a JSON object")
    add("runtime_evidence_sha256", bool(SHA256_RE.fullmatch(declared_artifact_sha)) and declared_artifact_sha == actual_artifact_sha, "declared evidence SHA-256 matches supplied bytes")
    add("runtime_evidence_schema", get(artifact or {}, "schema") == EXPECTED_APP_EVIDENCE_SCHEMA, "evidence is application E2E schema")
    add("runtime_evidence_scope", get(artifact or {}, "scope") == EXPECTED_APP_SCOPE, "evidence scope is APPLICATION_E2E")
    add("runtime_source_commit", get(artifact or {}, "source.commit_sha") == commit and bool(commit), "evidence commit matches dossier commit")
    add("runtime_source_archive", get(artifact or {}, "source.archive_sha256") == source_archive_sha and bool(source_archive_sha), "evidence archive matches dossier source archive")
    add("runtime_certifier_sha256", bool(SHA256_RE.fullmatch(str(get(artifact or {}, "certifier_sha256", "")))), "certifier SHA-256 recorded in evidence")
    add("runtime_sdk_version", get(artifact or {}, "sdk.version") == EXPECTED_SDK_VERSION, "Strands SDK version is pinned")
    add("runtime_sdk_wheel", get(artifact or {}, "sdk.wheel_sha256") == EXPECTED_SDK_WHEEL_SHA256, "official Strands wheel SHA-256 matches")
    add("runtime_artifact_status", get(artifact or {}, "status") == "PASS" and get(artifact or {}, "checks_passed") == get(artifact or {}, "checks_total") and get(artifact or {}, "checks_total", 0) >= 17, "application artifact reports all checks passed")
    add("runtime_artifact_classification", get(artifact or {}, "runtime") == "REAL_STRANDS", "application artifact classifies runtime REAL_STRANDS")
    add("runtime_artifact_effect", get(artifact or {}, "external_effect") == "SIMULATED", "application artifact truthfully labels external effect SIMULATED")
    add("runtime_resolution_truth", get(artifact or {}, "human_resolution") == "CLIENT_RESOLUTION_UNVERIFIED_ACTOR", "actor identity is not overstated")

    add("strands_runtime", get(data, "runtime.agent") == "REAL_STRANDS", "dossier runtime classified REAL_STRANDS")
    add("integrated_certification", get(data, "runtime.certification_status") == "PASS" and get(data, "runtime.certification_checks", 0) >= 17, "integrated certifier reports at least 17/17")
    add("interrupt", get(data, "runtime.interrupt") == "REAL", "real Confirm interrupt observed")
    add("resume", get(data, "runtime.resume") == "REAL", "real interruptResponse resume observed")
    add("single_effect", get(data, "runtime.effect_count") == 1, "effect_count equals one")
    add("replay", get(data, "runtime.replay") == "SAME_RECEIPT_NO_SECOND_EFFECT", "replay preserved receipt without duplicate effect")
    add("tamper", get(data, "runtime.tamper") == "BLOCKED", "US$8,751 mutation blocked")
    add("external_truth", get(data, "runtime.external_effect") == "SIMULATED", "external effect truthfully labeled SIMULATED")

    add("public_name", get(data, "product.public_name") == "VÉRTICE", "public name is VÉRTICE")
    add("tagline", get(data, "product.tagline") == "The agent works. You decide.", "approved public tagline is consistent")
    add("readme", get(data, "submission.readme") is True, "README present")
    add("architecture", get(data, "submission.architecture_diagram") is True, "architecture diagram present")
    add("license", get(data, "submission.license") in {"MIT", "Apache-2.0"}, "allowed open-source license present")
    add("private_material_excluded", get(data, "submission.private_material_excluded") is True, "private research excluded")

    if stage in {"candidate", "submission"}:
        video_commit = str(get(data, "video.commit_sha", ""))
        add("video_commit", video_commit == commit and bool(commit), "video uses certified commit")
        add("video_evidence", get(data, "video.evidence_file_sha256") == declared_artifact_sha and bool(declared_artifact_sha), "video references certified runtime evidence")
        duration = get(data, "video.duration_seconds")
        add("video_duration", isinstance(duration, (int, float)) and 0 < duration <= 300, "video duration is within 5 minutes")
        add("video_truth_labels", get(data, "video.truth_labels_visible") is True, "REAL/SIMULATED/REPLAY labels visible")

    if stage == "submission":
        add("repository_public", get(data, "submission.repository_public") is True, "repository public and accessible", "Manuel")
        add("video_public", get(data, "submission.video_public") is True, "YouTube/Vimeo video public", "Manuel")
        add("aws_builder_id", get(data, "submission.aws_builder_id_confirmed") is True, "AWS Builder ID confirmed", "Manuel")
        add("devpost_fields", get(data, "submission.devpost_fields_complete") is True, "Devpost fields complete", "Manuel")
        add("manual_authorization", get(data, "submission.manual_send_authorized") is True, "Manuel authorized final submission", "Manuel")

    failed = [c for c in checks if c.status == "FAIL"]
    manual = [c for c in failed if c.owner == "Manuel"]
    provenance_names = {name for name in (
        "runtime_evidence_supplied", "runtime_evidence_json", "runtime_evidence_sha256",
        "runtime_evidence_schema", "runtime_evidence_scope", "runtime_source_commit",
        "runtime_source_archive", "runtime_certifier_sha256", "runtime_sdk_version",
        "runtime_sdk_wheel", "runtime_artifact_status", "runtime_artifact_classification",
        "runtime_artifact_effect", "runtime_resolution_truth",
    )}
    red_names = {"strands_runtime", "integrated_certification", "secrets"} | provenance_names
    if failed:
        status = "RED" if stage == "submission" or any(c.name in red_names for c in failed) else "AMBER"
    else:
        status = "GREEN"
    return {
        "schema": "vertice.release-gate.v2",
        "stage": stage,
        "status": status,
        "summary": {"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
        "manual_blockers": [c.name for c in manual],
        "checks": [asdict(c) for c in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--runtime-evidence", type=Path, required=True)
    parser.add_argument("--stage", choices=("preflight", "candidate", "submission"), default="preflight")
    parser.add_argument("--output", type=Path, default=Path("release-gate-result.json"))
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = evaluate(data, args.stage, args.runtime_evidence.read_bytes())
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
