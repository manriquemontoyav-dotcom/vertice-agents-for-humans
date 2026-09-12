#!/usr/bin/env python3
"""Bind VÉRTICE browser proof and demo metadata to one certified candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_STATES = {"READY", "INTERRUPTED", "COMMITTED", "REPLAY_BLOCKED", "MUTATION_BLOCKED", "DENIED"}
REQUIRED_SCREENSHOTS = {"INTERRUPTED", "COMMITTED", "REPLAY_BLOCKED", "MUTATION_BLOCKED", "DENIED"}
REQUIRED_VIDEO_SECTIONS = {"problem", "audience", "why_it_matters", "working_demo", "architecture"}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts and "\\" not in value


def evaluate(
    dossier: dict[str, Any],
    app_evidence: dict[str, Any],
    app_evidence_sha: str,
    browser_evidence: dict[str, Any],
    browser_evidence_sha: str,
    candidate_sha: str,
    video_sha: str,
    video: dict[str, Any],
    screenshots_dir: Path,
) -> dict[str, Any]:
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append(Check(name, "PASS" if ok else "FAIL", detail))

    commit = str(get(dossier, "build.commit_sha", ""))
    archive_sha = str(get(dossier, "build.source_archive_sha256", ""))
    declared_candidate_sha = str(get(dossier, "build.candidate_sha256", ""))
    declared_app_sha = str(get(dossier, "runtime.evidence_file_sha256", ""))

    add("dossier_schema", get(dossier, "schema") == "vertice.release-evidence.v2", "release dossier v2")
    add("commit_format", bool(SHA1_RE.fullmatch(commit)), "40-character commit SHA")
    add("archive_hash_format", bool(SHA256_RE.fullmatch(archive_sha)), "source archive SHA-256")
    add("candidate_bytes_bound", declared_candidate_sha == candidate_sha and bool(SHA256_RE.fullmatch(candidate_sha)), "candidate ZIP bytes match dossier")
    add("application_evidence_bytes_bound", declared_app_sha == app_evidence_sha and bool(SHA256_RE.fullmatch(app_evidence_sha)), "application evidence bytes match dossier")

    add("application_schema", get(app_evidence, "schema") == "vertice.application-e2e.v1", "application E2E schema")
    add("application_scope", get(app_evidence, "scope") == "APPLICATION_E2E", "application E2E scope")
    add("application_pass", get(app_evidence, "status") == "PASS" and get(app_evidence, "checks_passed") == get(app_evidence, "checks_total") and get(app_evidence, "checks_total", 0) >= 17, "application checks passed")
    add("application_commit", get(app_evidence, "source.commit_sha") == commit and bool(commit), "application evidence commit matches")
    add("application_archive", get(app_evidence, "source.archive_sha256") == archive_sha and bool(archive_sha), "application evidence archive matches")
    add("application_runtime", get(app_evidence, "runtime") == "REAL_STRANDS", "application runtime is REAL_STRANDS")
    add("application_external_truth", get(app_evidence, "external_effect") == "SIMULATED", "external effect is SIMULATED")

    add("browser_schema", get(browser_evidence, "schema") == "vertice.browser-e2e.v1", "browser E2E schema")
    add("browser_scope", get(browser_evidence, "scope") == "BROWSER_APPLICATION_E2E", "browser application scope")
    add("browser_pass", get(browser_evidence, "status") == "PASS" and get(browser_evidence, "checks_passed") == get(browser_evidence, "checks_total") and get(browser_evidence, "checks_total", 0) >= 8, "browser checks passed")
    add("browser_commit", get(browser_evidence, "source.commit_sha") == commit and bool(commit), "browser evidence commit matches")
    add("browser_archive", get(browser_evidence, "source.archive_sha256") == archive_sha and bool(archive_sha), "browser evidence archive matches")
    add("browser_application_binding", get(browser_evidence, "application_evidence_sha256") == app_evidence_sha and bool(app_evidence_sha), "browser proof references application evidence")
    add("browser_runtime", get(browser_evidence, "runtime") == "REAL_STRANDS", "browser observed REAL_STRANDS")
    add("browser_same_session", get(browser_evidence, "same_runtime_session") is True, "UI and API use same runtime session")
    add("browser_actor_truth", get(browser_evidence, "decision_actor") == "OBSERVED_UI_CLICK_UNVERIFIED_ACTOR", "browser does not overstate actor identity")
    add("browser_external_truth", get(browser_evidence, "external_effect") == "SIMULATED", "browser proof labels external effect SIMULATED")
    states = {str(item).upper() for item in get(browser_evidence, "observed_states", []) if isinstance(item, str)}
    add("browser_states", REQUIRED_STATES <= states, "all required UI/runtime states observed")

    screenshot_entries = get(browser_evidence, "screenshots", [])
    screenshot_entries = screenshot_entries if isinstance(screenshot_entries, list) else []
    labels: set[str] = set()
    paths_valid = True
    hashes_valid = True
    files_present = True
    no_symlinks = True
    for entry in screenshot_entries:
        if not isinstance(entry, dict):
            paths_valid = hashes_valid = files_present = False
            continue
        label = str(entry.get("label", "")).upper()
        rel = str(entry.get("file", ""))
        declared = str(entry.get("sha256", ""))
        labels.add(label)
        if not safe_relative_path(rel):
            paths_valid = False
            continue
        path = screenshots_dir / rel
        if not path.exists() or not path.is_file():
            files_present = False
            continue
        cursor = screenshots_dir
        if any((cursor := cursor / part).is_symlink() for part in PurePosixPath(rel).parts):
            no_symlinks = False
            continue
        if not path.resolve().is_relative_to(screenshots_dir.resolve()):
            paths_valid = False
            continue
        if not SHA256_RE.fullmatch(declared) or sha256_file(path) != declared:
            hashes_valid = False
    add("screenshot_labels", REQUIRED_SCREENSHOTS <= labels, "required browser states have screenshots")
    add("screenshot_paths", paths_valid, "screenshot paths are relative and traversal-free")
    add("screenshot_files", files_present and bool(screenshot_entries), "screenshot files exist")
    add("screenshot_symlinks", no_symlinks, "screenshots are regular files")
    add("screenshot_hashes", hashes_valid and bool(screenshot_entries), "screenshot hashes match exact bytes")

    add("video_schema", get(video, "schema") == "vertice.video-freeze.v1", "video freeze schema")
    add("video_bytes_bound", get(video, "video_sha256") == video_sha and bool(SHA256_RE.fullmatch(video_sha)), "video hash matches exact bytes")
    add("video_commit", get(video, "source.commit_sha") == commit and bool(commit), "video commit matches certified commit")
    add("video_candidate", get(video, "candidate_sha256") == candidate_sha and bool(candidate_sha), "video references exact candidate ZIP")
    add("video_application_evidence", get(video, "application_evidence_sha256") == app_evidence_sha and bool(app_evidence_sha), "video references application evidence")
    add("video_browser_evidence", get(video, "browser_evidence_sha256") == browser_evidence_sha and bool(browser_evidence_sha), "video references browser evidence")
    duration = get(video, "duration_seconds")
    add("video_duration", isinstance(duration, (int, float)) and not isinstance(duration, bool) and 0 < duration <= 300, "video is no longer than five minutes")
    width = get(video, "resolution.width")
    height = get(video, "resolution.height")
    add("video_resolution", isinstance(width, int) and isinstance(height, int) and width >= 1280 and height >= 720, "video resolution is at least 1280x720")
    add("video_truth_labels", get(video, "truth_labels_visible") is True, "REAL/SIMULATED/REPLAY labels are visible")
    sections = {str(item) for item in get(video, "sections", []) if isinstance(item, str)}
    add("video_required_sections", REQUIRED_VIDEO_SECTIONS <= sections, "problem, audience, impact, working demo and architecture included")
    add("video_language", get(video, "language") == "English", "submission video is in English")

    failed = [item for item in checks if item.status == "FAIL"]
    return {
        "schema": "vertice.demo-freeze-gate.v1",
        "status": "GREEN" if not failed else "RED",
        "summary": {"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
        "checks": [asdict(item) for item in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dossier", type=Path, required=True)
    parser.add_argument("--application-evidence", type=Path, required=True)
    parser.add_argument("--browser-evidence", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--video-metadata", type=Path, required=True)
    parser.add_argument("--video-file", type=Path, required=True)
    parser.add_argument("--screenshots-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("demo-freeze-result.json"))
    args = parser.parse_args()

    dossier = json.loads(args.dossier.read_text(encoding="utf-8"))
    app_raw = args.application_evidence.read_bytes()
    browser_raw = args.browser_evidence.read_bytes()
    result = evaluate(
        dossier,
        json.loads(app_raw.decode("utf-8")),
        hashlib.sha256(app_raw).hexdigest(),
        json.loads(browser_raw.decode("utf-8")),
        hashlib.sha256(browser_raw).hexdigest(),
        sha256_file(args.candidate),
        sha256_file(args.video_file),
        json.loads(args.video_metadata.read_text(encoding="utf-8")),
        args.screenshots_dir,
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
