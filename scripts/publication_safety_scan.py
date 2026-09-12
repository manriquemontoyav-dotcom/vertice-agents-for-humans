from pathlib import Path
import re, sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git'}
FORBIDDEN_NAMES = {'.env', '.DS_Store'}
FORBIDDEN_SUFFIXES = {'.pyc', '.p12', '.pfx', '.pem', '.key', '.sqlite', '.sqlite3'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.yml', '.yaml', '.html', '.svg', '.toml', '.json', ''}
PATTERNS = {
    'internal_path': re.compile(r'/(?:mnt/data|home/oai)(?:/|\\b)', re.I),
    'sandbox_uri': re.compile(r'sandbox:/', re.I),
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'aws_access_key': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'github_token': re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}\b'),
    'slack_token': re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b'),
    'openai_key_like': re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'),
    'sensitive_strategy_marker': re.compile(r'\b(?:private novelty|prior[- ]art matrix|patent strategy|trade secret)\b', re.I),
}

issues=[]
for p in ROOT.rglob('*'):
    if not p.is_file() or any(part in SKIP for part in p.parts):
        continue
    if p.resolve() == Path(__file__).resolve():
        continue
    rel=p.relative_to(ROOT)
    if p.name in FORBIDDEN_NAMES or p.suffix.lower() in FORBIDDEN_SUFFIXES or '__pycache__' in p.parts:
        issues.append(f'forbidden_artifact:{rel}')
        continue
    if p.suffix.lower() not in TEXT_SUFFIXES:
        continue
    try: text=p.read_text(encoding='utf-8')
    except UnicodeDecodeError: continue
    for name, rx in PATTERNS.items():
        if rx.search(text): issues.append(f'{name}:{rel}')

if issues:
    print('PUBLICATION SAFETY SCAN: FAIL')
    for item in issues: print('-', item)
    sys.exit(2)
print('PUBLICATION SAFETY SCAN: PASS')
