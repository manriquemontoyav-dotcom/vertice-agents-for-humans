from __future__ import annotations
import hashlib, json, os, platform, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SRC=ROOT/'src'
sys.path.insert(0,str(SRC))

from afh.strands_runtime_harness import run_verified_flow
from afh.ci_evidence import assess, EXPECTED_STRANDS_VERSION, EXPECTED_WHEEL_SHA256

wheel_path=os.getenv('AFH_STRANDS_WHEEL')
wheel_hash_verified=False
wheel_sha256=None
if wheel_path and Path(wheel_path).exists():
    wheel_sha256=hashlib.sha256(Path(wheel_path).read_bytes()).hexdigest()
    wheel_hash_verified=(wheel_sha256==EXPECTED_WHEEL_SHA256)

result=run_verified_flow()
assessment=assess(result,wheel_hash_verified=wheel_hash_verified)

evidence={
    'schema':'afh.strands-real-pass.v1',
    'generated_at_utc':datetime.now(timezone.utc).isoformat(),
    'pass':assessment.passed,
    'assessment_reasons':assessment.reasons,
    'expected_strands_version':EXPECTED_STRANDS_VERSION,
    'wheel':{
        'path':wheel_path,
        'sha256':wheel_sha256,
        'expected_sha256':EXPECTED_WHEEL_SHA256,
        'verified':wheel_hash_verified,
    },
    'runtime':result,
    'environment':{
        'python':sys.version,
        'platform':platform.platform(),
        'github_sha':os.getenv('GITHUB_SHA'),
        'github_run_id':os.getenv('GITHUB_RUN_ID'),
        'github_run_attempt':os.getenv('GITHUB_RUN_ATTEMPT'),
    },
}
out=ROOT/'STRANDS_REAL_PASS.json'
out.write_text(json.dumps(evidence,indent=2,sort_keys=True),encoding='utf-8')
print(json.dumps(evidence,indent=2,sort_keys=True))
raise SystemExit(0 if assessment.passed else 3)
