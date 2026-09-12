import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReleaseHardeningTests(unittest.TestCase):
    def test_verify_publication_script_exists(self):
        self.assertTrue((ROOT/'scripts'/'verify_publication.py').is_file())
    def test_ci_uses_verification_runner(self):
        wf=(ROOT/'.github'/'workflows'/'strands-real-pass.yml').read_text()
        self.assertIn('python scripts/verify_publication.py', wf)
        self.assertIn("PYTHONDONTWRITEBYTECODE: '1'", wf)
    def test_judge_quickstart_exists(self):
        self.assertTrue((ROOT/'JUDGE_QUICKSTART.md').is_file())
