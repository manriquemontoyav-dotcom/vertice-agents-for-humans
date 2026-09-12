import subprocess, sys, unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]

class PublicationSafetyTests(unittest.TestCase):
    def test_publication_safety_scan(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/publication_safety_scan.py')],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_no_generated_bytecode_committed(self):
        self.assertFalse(list(ROOT.rglob('*.pyc')))
        self.assertFalse([p for p in ROOT.rglob('__pycache__') if p.is_dir()])

if __name__=='__main__': unittest.main()
