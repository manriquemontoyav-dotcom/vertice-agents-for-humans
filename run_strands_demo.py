import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/'src'))
from afh.strands_runtime_harness import run_verified_flow
result=run_verified_flow()
print(json.dumps(result,indent=2,sort_keys=True))
raise SystemExit(0 if result.get('status')=='PASS' else 2)
