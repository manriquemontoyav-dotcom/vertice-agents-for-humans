import json, sys, importlib.util
from importlib.metadata import version, PackageNotFoundError

expected='1.54.0'
status={'python':sys.version.split()[0], 'strands_installed': bool(importlib.util.find_spec('strands')), 'expected':expected}
try: status['strands_version']=version('strands-agents')
except PackageNotFoundError: status['strands_version']=None
status['ready_for_strands_runtime']=(status['strands_version']==expected)
print(json.dumps(status,indent=2,sort_keys=True))
sys.exit(0 if status['ready_for_strands_runtime'] else 2)
