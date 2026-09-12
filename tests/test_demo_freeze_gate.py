import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from demo_freeze_gate import evaluate, sha256_file


COMMIT = "a" * 40
ARCHIVE_SHA = "b" * 64


class DemoFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / "candidate.zip"
        self.candidate.write_bytes(b"candidate fixture bytes")
        self.candidate_sha = sha256_file(self.candidate)
        self.video_file = self.root / "demo.mp4"
        self.video_file.write_bytes(b"simulated video fixture bytes")
        self.video_sha = sha256_file(self.video_file)
        self.shots = self.root / "shots"
        self.shots.mkdir()
        labels = ["INTERRUPTED", "COMMITTED", "REPLAY_BLOCKED", "MUTATION_BLOCKED", "DENIED"]
        entries = []
        for label in labels:
            path = self.shots / f"{label.lower()}.png"
            path.write_bytes(f"simulated screenshot {label}".encode())
            entries.append({"label": label, "file": path.name, "sha256": sha256_file(path)})

        self.app = {
            "schema": "vertice.application-e2e.v1", "scope": "APPLICATION_E2E",
            "status": "PASS", "checks_passed": 17, "checks_total": 17,
            "source": {"commit_sha": COMMIT, "archive_sha256": ARCHIVE_SHA},
            "runtime": "REAL_STRANDS", "external_effect": "SIMULATED",
        }
        self.app_raw = (json.dumps(self.app, sort_keys=True) + "\n").encode()
        self.app_sha = hashlib.sha256(self.app_raw).hexdigest()
        self.browser = {
            "schema": "vertice.browser-e2e.v1", "scope": "BROWSER_APPLICATION_E2E",
            "status": "PASS", "checks_passed": 8, "checks_total": 8,
            "source": {"commit_sha": COMMIT, "archive_sha256": ARCHIVE_SHA},
            "application_evidence_sha256": self.app_sha,
            "runtime": "REAL_STRANDS", "same_runtime_session": True,
            "decision_actor": "OBSERVED_UI_CLICK_UNVERIFIED_ACTOR",
            "external_effect": "SIMULATED",
            "observed_states": ["READY", "INTERRUPTED", "COMMITTED", "REPLAY_BLOCKED", "MUTATION_BLOCKED", "DENIED"],
            "screenshots": entries,
        }
        self.browser_raw = (json.dumps(self.browser, sort_keys=True) + "\n").encode()
        self.browser_sha = hashlib.sha256(self.browser_raw).hexdigest()
        self.dossier = {
            "schema": "vertice.release-evidence.v2",
            "build": {"commit_sha": COMMIT, "source_archive_sha256": ARCHIVE_SHA, "candidate_sha256": self.candidate_sha},
            "runtime": {"evidence_file_sha256": self.app_sha},
        }
        self.video = {
            "schema": "vertice.video-freeze.v1",
            "video_sha256": self.video_sha,
            "source": {"commit_sha": COMMIT},
            "candidate_sha256": self.candidate_sha,
            "application_evidence_sha256": self.app_sha,
            "browser_evidence_sha256": self.browser_sha,
            "duration_seconds": 270,
            "resolution": {"width": 1920, "height": 1080},
            "truth_labels_visible": True,
            "sections": ["problem", "audience", "why_it_matters", "working_demo", "architecture"],
            "language": "English",
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_gate(self, dossier=None, app=None, browser=None, video=None, candidate_sha=None, app_sha=None, browser_sha=None, video_sha=None):
        return evaluate(
            dossier or self.dossier,
            app or self.app,
            app_sha or self.app_sha,
            browser or self.browser,
            browser_sha or self.browser_sha,
            candidate_sha or self.candidate_sha,
            video_sha or self.video_sha,
            video or self.video,
            self.shots,
        )

    def test_complete_fixture_is_green_39_of_39(self):
        result = self.run_gate()
        self.assertEqual((result["status"], result["summary"]), ("GREEN", {"checks": 39, "passed": 39, "failed": 0}))

    def test_candidate_bytes_mismatch_is_red(self):
        self.assertEqual(self.run_gate(candidate_sha="f" * 64)["status"], "RED")

    def test_application_evidence_bytes_mismatch_is_red(self):
        self.assertEqual(self.run_gate(app_sha="f" * 64)["status"], "RED")

    def test_browser_not_bound_to_application_is_red(self):
        browser = copy.deepcopy(self.browser); browser["application_evidence_sha256"] = "f" * 64
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_browser_evidence_hash_mismatch_is_red(self):
        self.assertEqual(self.run_gate(browser_sha="f" * 64)["status"], "RED")

    def test_missing_required_state_is_red(self):
        browser = copy.deepcopy(self.browser); browser["observed_states"].remove("DENIED")
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_screenshot_hash_mismatch_is_red(self):
        browser = copy.deepcopy(self.browser); browser["screenshots"][0]["sha256"] = "f" * 64
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_screenshot_path_traversal_is_red(self):
        browser = copy.deepcopy(self.browser); browser["screenshots"][0]["file"] = "../outside.png"
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_screenshot_symlink_is_red(self):
        outside = self.root / "outside.png"
        outside.write_bytes(b"outside screenshot fixture")
        link = self.shots / "linked.png"
        link.symlink_to(outside)
        browser = copy.deepcopy(self.browser)
        browser["screenshots"][0]["file"] = link.name
        browser["screenshots"][0]["sha256"] = sha256_file(outside)
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_actor_identity_overclaim_is_red(self):
        browser = copy.deepcopy(self.browser); browser["decision_actor"] = "VERIFIED_HUMAN"
        self.assertEqual(self.run_gate(browser=browser)["status"], "RED")

    def test_video_from_other_commit_is_red(self):
        video = copy.deepcopy(self.video); video["source"]["commit_sha"] = "f" * 40
        self.assertEqual(self.run_gate(video=video)["status"], "RED")

    def test_video_bytes_mismatch_is_red(self):
        self.assertEqual(self.run_gate(video_sha="f" * 64)["status"], "RED")

    def test_video_over_five_minutes_is_red(self):
        video = copy.deepcopy(self.video); video["duration_seconds"] = 301
        self.assertEqual(self.run_gate(video=video)["status"], "RED")

    def test_video_missing_problem_section_is_red(self):
        video = copy.deepcopy(self.video); video["sections"].remove("problem")
        self.assertEqual(self.run_gate(video=video)["status"], "RED")

    def test_non_english_video_is_red(self):
        video = copy.deepcopy(self.video); video["language"] = "Spanish"
        self.assertEqual(self.run_gate(video=video)["status"], "RED")


if __name__ == "__main__":
    unittest.main()
