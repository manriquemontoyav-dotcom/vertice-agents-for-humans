import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from final_submission_gate import evaluate


COMMIT = "a" * 40


class FinalSubmissionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = {}
        candidate = self.root / "candidate.zip"
        candidate.write_bytes(b"synthetic candidate bytes")
        self.paths["candidate"] = candidate
        candidate_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()

        app = {
            "schema": "vertice.application-e2e.v1", "scope": "APPLICATION_E2E",
            "status": "PASS", "checks_passed": 17, "checks_total": 17,
            "runtime": "REAL_STRANDS", "external_effect": "SIMULATED",
            "source": {"commit_sha": COMMIT, "archive_sha256": "b" * 64},
        }
        self.write_json("application", app)
        app_sha = hashlib.sha256(self.paths["application"].read_bytes()).hexdigest()
        dossier = {
            "schema": "vertice.release-evidence.v2",
            "build": {"commit_sha": COMMIT, "candidate_sha256": candidate_sha},
            "runtime": {"evidence_file_sha256": app_sha},
        }
        self.write_json("dossier", dossier)
        self.write_json("release", {"schema": "vertice.release-gate.v2", "status": "GREEN", "summary": {"checks": 38, "passed": 38, "failed": 0}})
        self.write_json("demo", {"schema": "vertice.demo-freeze-gate.v1", "status": "GREEN", "summary": {"checks": 39, "passed": 39, "failed": 0}})
        self.write_json("compliance", {"schema": "vertice.submission-compliance-gate.v1", "status": "GREEN", "summary": {"checks": 38, "passed": 38, "failed": 0}})
        self.manifest = {
            "schema": "vertice.final-submission-manifest.v1",
            "source": {"commit_sha": COMMIT},
            "artifacts": {"candidate_sha256": candidate_sha},
            "public": {
                "repository_url": "https://github.com/owner/project",
                "video_url": "https://youtu.be/video-id",
                "repository_http_status": 200, "video_http_status": 200,
                "checked_at_utc": "2026-09-13T12:00:00Z",
            },
            "manual": {
                "aws_builder_id_confirmed": True, "devpost_story_complete": True,
                "devpost_media_complete": True, "devpost_links_match": True,
            },
            "authorization": {
                "commit_sha": COMMIT, "candidate_sha256": candidate_sha,
                "decision": "MANUEL_AUTHORIZED_SUBMISSION",
            },
        }
        for name in ("dossier", "application", "release", "demo", "compliance"):
            self.manifest["artifacts"][f"{name}_sha256"] = hashlib.sha256(self.paths[name].read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, name, data):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
        self.paths[name] = path

    def result(self, stage="candidate", manifest=None):
        return evaluate(manifest or self.manifest, stage, self.paths)

    def test_candidate_fixture_is_green_30_of_30(self):
        result = self.result()
        self.assertEqual((result["status"], result["summary"]), ("GREEN", {"checks": 30, "passed": 30, "failed": 0}))

    def test_submission_fixture_is_green_42_of_42(self):
        result = self.result("submission")
        self.assertEqual((result["status"], result["summary"]), ("GREEN", {"checks": 42, "passed": 42, "failed": 0}))

    def test_candidate_bytes_change_is_red(self):
        self.paths["candidate"].write_bytes(b"changed")
        self.assertEqual(self.result()["status"], "RED")

    def test_application_artifact_change_is_red(self):
        self.paths["application"].write_bytes(self.paths["application"].read_bytes() + b" ")
        self.assertEqual(self.result()["status"], "RED")

    def test_sdk_contract_scope_cannot_pass(self):
        app = json.loads(self.paths["application"].read_text())
        app["scope"] = "SDK_CONTRACT"
        self.write_json("application", app)
        self.assertEqual(self.result()["status"], "RED")

    def test_simulated_runtime_cannot_pass(self):
        app = json.loads(self.paths["application"].read_text())
        app["runtime"] = "SIMULATED_DRIVER"
        self.write_json("application", app)
        self.assertEqual(self.result()["status"], "RED")

    def test_red_compliance_cannot_pass(self):
        self.write_json("compliance", {"status": "RED", "summary": {"checks": 38, "passed": 37, "failed": 1}})
        self.assertEqual(self.result()["status"], "RED")

    def test_unsupported_video_host_is_red(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["public"]["video_url"] = "https://videos.invalid/demo"
        self.assertEqual(self.result("publication", manifest)["status"], "RED")

    def test_submission_without_authorization_is_red_and_manual_blocker(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["authorization"]["decision"] = "PENDING"
        result = self.result("submission", manifest)
        self.assertEqual(result["status"], "RED")
        self.assertIn("manual_authorization", result["manual_blockers"])

    def test_authorization_for_other_candidate_is_red(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["authorization"]["candidate_sha256"] = "f" * 64
        self.assertEqual(self.result("submission", manifest)["status"], "RED")


if __name__ == "__main__":
    unittest.main()
