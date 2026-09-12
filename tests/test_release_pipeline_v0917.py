import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ReleasePipelineTests(unittest.TestCase):
    def test_application_e2e_workflow_is_pinned_and_runs_full_gate(self):
        text=(ROOT/'.github/workflows/application-e2e-release-gate.yml').read_text(encoding='utf-8')
        self.assertIn('strands-agents==1.54.0', text)
        self.assertIn('ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c', text)
        self.assertIn('application_e2e_certifier.py', text)
        self.assertIn('--stage preflight', text)
        self.assertIn('uvicorn webapp:app', text)
    def test_regression_json_runner_reports_real_counts(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/'test_ok.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n',encoding='utf-8')
            out=t/'r.json'
            p=subprocess.run([sys.executable,str(ROOT/'scripts/run_regression_json.py'),'--start-dir',str(t),'--output',str(out)],cwd=ROOT)
            self.assertEqual(p.returncode,0)
            d=json.loads(out.read_text())
            self.assertEqual(d['tests_run'],1); self.assertEqual(d['passed'],1); self.assertEqual(d['failures'],0); self.assertEqual(d['errors'],0)
    def test_dossier_builder_records_repository_mit_license(self):
        text=(ROOT/'scripts/build_release_dossier.py').read_text(encoding='utf-8')
        self.assertIn("'license':'MIT'", text)
        self.assertNotIn("'license':'Apache-2.0'", text)

    def test_release_gate_accepts_certifier_growth_beyond_17_checks(self):
        text=(ROOT/'release_gate.py').read_text(encoding='utf-8')
        self.assertIn('get(data, "runtime.certification_checks", 0) >= 17', text)
        self.assertNotIn('get(data, "runtime.certification_checks") == 17', text)

    def test_dossier_builder_refuses_runtime_archive_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); archive=t/'source.zip'; archive.write_bytes(b'actual')
            runtime=t/'runtime.json'; runtime.write_text(json.dumps({'scope':'APPLICATION_E2E','source':{'commit_sha':'a'*40,'archive_sha256':'0'*64}}))
            reg=t/'reg.json'; reg.write_text(json.dumps({'passed':1,'failures':0,'errors':0,'skipped':0}))
            p=subprocess.run([sys.executable,str(ROOT/'scripts/build_release_dossier.py'),'--commit-sha','a'*40,'--source-archive',str(archive),'--runtime-evidence',str(runtime),'--regression',str(reg),'--workflow-run-id','1','--output',str(t/'out.json')],cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('archive mismatch',p.stderr+p.stdout)

if __name__=='__main__': unittest.main()
