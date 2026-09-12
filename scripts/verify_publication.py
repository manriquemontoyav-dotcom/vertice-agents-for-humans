from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'

def run(label: str, args: list[str]) -> None:
    print(f'== {label} ==')
    p = subprocess.run(args, cwd=ROOT, env=env)
    if p.returncode:
        raise SystemExit(p.returncode)

run('pre-test publication safety', [sys.executable, 'scripts/publication_safety_scan.py'])
run('public regression', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
run('post-test publication safety', [sys.executable, 'scripts/publication_safety_scan.py'])
print('AFH PUBLICATION VERIFICATION: PASS')
