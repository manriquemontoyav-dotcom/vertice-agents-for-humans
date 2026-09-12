#!/usr/bin/env python3
"""Fail-closed public submission compliance gate for VÉRTICE."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PUBLIC_IDENTITY = ("VÉRTICE", "Agents for Humans", "The agent works. You decide.")
TRUTH_LABELS = ("REAL", "SIMULATED", "REPLAY")
README_SECTIONS = {
    "problem": ("## problem", "## the problem"),
    "audience": ("## who it is for", "## who it's for", "## audience"),
    "impact": ("## why it matters", "## impact"),
    "features": ("## features", "## what it does"),
    "architecture": ("## architecture",),
    "installation": ("## installation", "## install"),
    "running": ("## running", "## run", "## quickstart"),
    "testing": ("## testing", "## tests"),
}
FORBIDDEN_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".env", "private", "ip-private", "novelty"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".pem", ".key", ".sqlite", ".sqlite3", ".db"}
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|TBD|CHANGEME|YOUR_[A-Z0-9_]+)\b|<insert[^>]*>|example\.com", re.I)
SECRET_RES = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
)
OVERCLAIM_RE = re.compile(r"\b(?:patent pending|patented technology|guaranteed to win|production[- ]ready)\b", re.I)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    category: str


def all_files(root: Path) -> list[Path]:
    return sorted((path for path in root.rglob("*") if path.is_file() or path.is_symlink()), key=lambda p: p.as_posix())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def first_existing(root: Path, names: Iterable[str]) -> Path | None:
    for name in names:
        path = root / name
        if path.is_file() and not path.is_symlink():
            return path
    return None


def evaluate(root: Path) -> dict[str, Any]:
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str, category: str) -> None:
        checks.append(Check(name, "PASS" if ok else "FAIL", detail, category))

    valid_root = root.is_dir()
    add("source_directory", valid_root, "public candidate source directory exists", "package")
    files = all_files(root) if valid_root else []
    regular_files = [path for path in files if path.is_file() and not path.is_symlink()]
    relative = [path.relative_to(root) for path in files]

    symlinks = [str(path) for path in relative if (root / path).is_symlink()]
    add("no_symlinks", not symlinks, "no symbolic links", "security")
    forbidden = []
    for path in relative:
        parts = {part.casefold() for part in path.parts}
        if parts & FORBIDDEN_PARTS or path.suffix.casefold() in FORBIDDEN_SUFFIXES or path.name.casefold().startswith(".env."):
            forbidden.append(path.as_posix())
    add("no_forbidden_artifacts", not forbidden, "no caches, credentials, databases, private material or Git history", "security")
    total_size = sum(path.stat().st_size for path in regular_files)
    add("repository_size", 0 < total_size <= 50 * 1024 * 1024, "source tree is nonempty and at most 50 MiB", "package")
    oversized = [path.relative_to(root).as_posix() for path in regular_files if path.stat().st_size > 5 * 1024 * 1024]
    add("individual_file_size", not oversized, "no individual file exceeds 5 MiB", "package")

    readme = first_existing(root, ("README.md", "README.rst"))
    readme_text = read_text(readme) if readme else ""
    readme_lower = readme_text.casefold()
    add("readme", bool(readme_text.strip()), "root README exists and is nonempty", "official")
    add("public_identity", all(term.casefold() in readme_lower for term in PUBLIC_IDENTITY), "approved VÉRTICE identity appears in README", "identity")
    for name, alternatives in README_SECTIONS.items():
        add(f"readme_{name}", any(item in readme_lower for item in alternatives), f"README contains {name} section", "presentation")
    add("truth_labels", all(label.casefold() in readme_lower for label in TRUTH_LABELS), "README explains REAL, SIMULATED and REPLAY", "truth")
    add("strands_explained", "strands agents" in readme_lower and ("interrupt" in readme_lower or "intervention" in readme_lower), "README explains non-trivial Strands use", "technical")
    add("differentiation_explained", "exact action" in readme_lower and "replay" in readme_lower and ("mutation" in readme_lower or "tamper" in readme_lower), "README explains exact action and replay/mutation defense", "technical")

    license_path = first_existing(root, ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    license_text = read_text(license_path) if license_path else ""
    license_ok = "permission is hereby granted, free of charge" in license_text.casefold() or "apache license" in license_text.casefold() and "version 2.0" in license_text.casefold()
    add("root_license", bool(license_text.strip()), "root license file exists", "official")
    add("allowed_license", license_ok, "license text is MIT or Apache-2.0", "official")

    architecture = first_existing(root, ("docs/ARCHITECTURE.md", "ARCHITECTURE.md"))
    architecture_text = read_text(architecture) if architecture else ""
    architecture_images = [path for path in regular_files if "architecture" in path.stem.casefold() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".svg"}]
    add("architecture_document", bool(architecture_text.strip()), "architecture document exists", "official")
    add("architecture_diagram", "```mermaid" in architecture_text.casefold() or bool(architecture_images), "architecture diagram is present", "official")

    testing = first_existing(root, ("docs/TESTING.md", "TESTING.md", "JUDGE_QUICKSTART.md"))
    testing_text = read_text(testing) if testing else ""
    testing_lower = testing_text.casefold()
    add("testing_instructions", bool(testing_text.strip()), "judge testing instructions exist", "official")
    add("testing_commands", ("pip install" in testing_lower or "uv sync" in testing_lower) and ("unittest" in testing_lower or "pytest" in testing_lower), "testing instructions include install and test commands", "reproducibility")

    dependency = first_existing(root, ("requirements.txt", "pyproject.toml"))
    dependency_text = read_text(dependency) if dependency else ""
    add("dependency_manifest", bool(dependency_text.strip()), "dependency manifest exists", "reproducibility")
    add("strands_dependency", "strands-agents" in dependency_text.casefold(), "Strands dependency is declared", "technical")
    workflows = [path for path in regular_files if path.relative_to(root).parts[:2] == (".github", "workflows") and path.suffix.casefold() in {".yml", ".yaml"}]
    add("ci_workflow", bool(workflows), "GitHub Actions workflow exists", "reproducibility")

    disclosure = first_existing(root, ("docs/CONTRIBUTIONS_AND_AI.md", "CONTRIBUTIONS_AND_AI.md", "AI_DISCLOSURE.md"))
    disclosure_text = read_text(disclosure) if disclosure else ""
    disclosure_lower = disclosure_text.casefold()
    add("contribution_disclosure", bool(disclosure_text.strip()), "human and AI contribution record exists", "provenance")
    add("human_ai_roles", "human" in disclosure_lower and ("ai assistance" in disclosure_lower or "ai-assisted" in disclosure_lower), "human and AI roles are distinguished", "provenance")
    add("preexisting_work", "pre-existing" in disclosure_lower or "preexisting" in disclosure_lower, "pre-existing work disclosure is explicit", "official")

    notices = first_existing(root, ("THIRD_PARTY_NOTICES.md", "docs/THIRD_PARTY_NOTICES.md"))
    notices_text = read_text(notices) if notices else ""
    add("third_party_notices", "strands" in notices_text.casefold(), "third-party notice covers Strands", "licensing")
    security = first_existing(root, ("SECURITY.md", "docs/SECURITY.md"))
    security_text = read_text(security) if security else ""
    add("security_document", bool(security_text.strip()), "security and privacy document exists", "security")

    docs_text = "\n".join(read_text(path) for path in regular_files if path.suffix.casefold() in {".md", ".rst", ".txt"})
    add("no_placeholders", not PLACEHOLDER_RE.search(docs_text), "public documentation has no TODO/TBD/example placeholders", "quality")
    add("no_overclaims", not OVERCLAIM_RE.search(docs_text), "public documentation avoids unsupported legal/product claims", "truth")
    secrets = []
    for path in regular_files:
        if path.stat().st_size > 2 * 1024 * 1024:
            continue
        text = read_text(path)
        if any(pattern.search(text) for pattern in SECRET_RES):
            secrets.append(path.relative_to(root).as_posix())
    add("no_secret_patterns", not secrets, "no common credential patterns detected", "security")

    python_files = [path for path in regular_files if path.suffix.casefold() == ".py"]
    python_corpus = "\n".join(read_text(path) for path in python_files)
    add("python_source", bool(python_files), "Python source files exist", "technical")
    add("strands_import", bool(re.search(r"(?:from\s+strands|import\s+strands)", python_corpus)), "source imports Strands Agents", "technical")
    ui = first_existing(root, ("static/index.html", "index.html"))
    add("user_interface", ui is not None and bool(read_text(ui).strip()), "user interface entrypoint exists", "design")

    failed = [check for check in checks if check.status == "FAIL"]
    categories: dict[str, dict[str, int]] = {}
    for item in checks:
        bucket = categories.setdefault(item.category, {"passed": 0, "failed": 0})
        bucket["passed" if item.status == "PASS" else "failed"] += 1
    return {
        "schema": "vertice.submission-compliance-gate.v1",
        "status": "GREEN" if not failed else "RED",
        "summary": {"checks": len(checks), "passed": len(checks) - len(failed), "failed": len(failed)},
        "categories": categories,
        "checks": [asdict(check) for check in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("submission-compliance-result.json"))
    args = parser.parse_args()
    result = evaluate(args.source)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
