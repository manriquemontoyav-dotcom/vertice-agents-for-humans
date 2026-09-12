import tempfile
import unittest
from pathlib import Path

from submission_compliance_gate import evaluate


MIT = """MIT License

Copyright (c) 2026 VÉRTICE contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files to deal in the Software
without restriction.
"""

README = """# VÉRTICE — Agents for Humans

> The agent works. You decide.

## Problem
Agents can cross consequential boundaries without exact authorization.
## Who it's for
People delegating real professional work to agents.
## Why it matters
Human authority must remain meaningful.
## Features
Exact action authorization, receipts and evidence.
## Architecture
Strands Agents uses an intervention and interrupt before the guarded tool.
## Installation
Install the pinned dependencies.
## Quickstart
Run the local server and open the Decision Inbox.
## Testing
Run the complete regression.

REAL identifies observed local execution. SIMULATED identifies the external effect.
REPLAY verifies the same receipt without a second effect. An exact action fingerprint
and mutation defense block tamper attempts.
"""


class ComplianceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.write("README.md", README)
        self.write("LICENSE", MIT)
        self.write("docs/ARCHITECTURE.md", "# Architecture\n\n```mermaid\ngraph LR\nA[Agent] --> B[Boundary]\n```\n")
        self.write("docs/TESTING.md", "# Testing\n\n`pip install -r requirements.txt` then `python -m unittest`.\n")
        self.write("docs/CONTRIBUTIONS_AND_AI.md", "# Contributions\n\nHuman product direction and review. AI assistance supported implementation and documentation. Pre-existing work: none incorporated.\n")
        self.write("THIRD_PARTY_NOTICES.md", "# Third-party notices\n\nStrands Agents SDK — Apache-2.0.\n")
        self.write("SECURITY.md", "# Security and privacy\n\nNo secrets. External effects are simulated.\n")
        self.write("requirements.txt", "strands-agents==1.54.0\nfastapi==0.116.1\n")
        self.write(".github/workflows/tests.yml", "name: tests\non: [push]\njobs: {}\n")
        self.write("src/afh/app.py", "from strands import Agent\n\ndef build():\n    return Agent\n")
        self.write("static/index.html", "<!doctype html><title>VÉRTICE</title><main>Decision Inbox</main>\n")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def assert_red_with(self, check_name):
        result = evaluate(self.root)
        self.assertEqual(result["status"], "RED")
        failed = {item["name"] for item in result["checks"] if item["status"] == "FAIL"}
        self.assertIn(check_name, failed)

    def test_complete_public_fixture_is_green_38_of_38(self):
        result = evaluate(self.root)
        self.assertEqual((result["status"], result["summary"]), ("GREEN", {"checks": 38, "passed": 38, "failed": 0}))

    def test_missing_source_directory_is_red(self):
        result = evaluate(self.root / "absent")
        self.assertEqual(result["status"], "RED")
        failed = {item["name"] for item in result["checks"] if item["status"] == "FAIL"}
        self.assertIn("source_directory", failed)

    def test_missing_license_is_red(self):
        (self.root / "LICENSE").unlink()
        self.assert_red_with("root_license")

    def test_invalid_license_is_red(self):
        self.write("LICENSE", "All rights reserved")
        self.assert_red_with("allowed_license")

    def test_missing_architecture_diagram_is_red(self):
        self.write("docs/ARCHITECTURE.md", "# Architecture\nNo rendered diagram yet.\n")
        self.assert_red_with("architecture_diagram")

    def test_missing_testing_commands_is_red(self):
        self.write("docs/TESTING.md", "# Testing\nRun it somehow.\n")
        self.assert_red_with("testing_commands")

    def test_missing_ai_disclosure_is_red(self):
        (self.root / "docs/CONTRIBUTIONS_AND_AI.md").unlink()
        self.assert_red_with("contribution_disclosure")

    def test_placeholder_is_red(self):
        self.write("docs/TESTING.md", "# Testing\nTODO: add pip install and unittest instructions.\n")
        self.assert_red_with("no_placeholders")

    def test_secret_pattern_is_red(self):
        # Build the inert fixture at runtime so the test suite itself never
        # contains a credential-shaped literal that external scanners flag.
        self.write("docs/leak.txt", "AKIA" + "1" * 16 + "\n")
        self.assert_red_with("no_secret_patterns")

    def test_symlink_is_red(self):
        (self.root / "linked-readme").symlink_to(self.root / "README.md")
        self.assert_red_with("no_symlinks")

    def test_private_directory_is_red(self):
        self.write("private/claims.md", "internal analysis")
        self.assert_red_with("no_forbidden_artifacts")

    def test_bytecode_cache_is_red(self):
        self.write("src/afh/__pycache__/app.pyc", "cache")
        self.assert_red_with("no_forbidden_artifacts")

    def test_overclaim_is_red(self):
        self.write("README.md", README + "\nThis is production-ready.\n")
        self.assert_red_with("no_overclaims")

    def test_missing_strands_import_is_red(self):
        self.write("src/afh/app.py", "def build():\n    return None\n")
        self.assert_red_with("strands_import")

    def test_missing_truth_label_is_red(self):
        self.write("README.md", README.replace("REPLAY", "repeat test"))
        self.assert_red_with("truth_labels")

    def test_missing_ui_is_red(self):
        (self.root / "static/index.html").unlink()
        self.assert_red_with("user_interface")


if __name__ == "__main__":
    unittest.main()
