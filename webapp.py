from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from afh.protocol import *
from afh.execution import *
from afh.demo_workflow import proposal_workflow

app=FastAPI(title='VÉRTICE — Agents for Humans',version='0.9.23',description='Exact-action human authority boundary for consequential agent actions.')
MANDATE=Mandate('Prepare and verify the best proposal; a human retains submission authority.')
STEPS=proposal_workflow(); ACTION=STEPS[-1].action
WORK=[s.name for s in STEPS[:-1]]
engine=BoundaryEngine(); compression=DecisionCompressionEngine().analyze(MANDATE,STEPS)
authority=DecisionAuthority()
store=ExecutionStore(':memory:'); guard=ExactlyOnceResumeGuard(authority,store)
ledger=EvidenceChain(); current_receipt=None; last_execution=None; effect_counter=0
for step in WORK: ledger.append('AUTO_WORK',{'step':step,'truth':'SIMULATED'})
boundary=engine.evaluate(MANDATE,ACTION)
ledger.append('BOUNDARY',{'mode':boundary.mode,'reasons':boundary.reasons,'action_hash':boundary.action_hash,'mandate_hash':boundary.mandate_hash})
TOOL_USE_ID='tooluse_afh_demo_001'

class ExecuteRequest(BaseModel):
    amount_usd: float|None=None
    recipient: str|None=None
    tool: str|None=None
    tool_use_id: str|None=None

@app.get('/',response_class=HTMLResponse)
def home(): return Path(__file__).with_name('static').joinpath('index.html').read_text()

@app.get('/api/state',include_in_schema=False)
def state():
    return {'version':'0.9.23','truth':'SIMULATED','work':WORK,'metrics':{
        'total_steps':compression.total_steps,'auto_steps':compression.auto_steps,
        'human_decisions':compression.human_decisions,'decision_compression_ratio':compression.compression_ratio},
        'decision':{'mode':boundary.mode,'reasons':boundary.reasons,
        'question':'Authorize submission of the exact US$8,750 proposal?',
        'action_hash':boundary.action_hash,'mandate_hash':boundary.mandate_hash,
        'amount_usd':8750,'recipient':'Demo Buyer','proposal_id':'AFH-DEMO-001','tool_use_id':TOOL_USE_ID},
        'receipt_issued': current_receipt is not None,
        'decision_receipt_id': current_receipt.receipt_id if current_receipt else None,
        'last_execution':last_execution,'ledger_valid':ledger.verify(),'evidence_root':ledger.root}

@app.post('/api/decision/approve',include_in_schema=False)
def approve():
    global current_receipt
    current_receipt=authority.approve(MANDATE,ACTION)
    ledger.append('HUMAN_DECISION',{'decision':'approve','action_hash':ACTION.action_hash,
        'mandate_hash':MANDATE.mandate_hash,'receipt_id':current_receipt.receipt_id,'truth':'SIMULATED'})
    return {'status':'APPROVED_EXACT_ACTION','receipt_id':current_receipt.receipt_id}

@app.post('/api/decision/reject',include_in_schema=False)
def reject():
    global current_receipt,last_execution
    current_receipt=authority.reject(MANDATE,ACTION); last_execution={'status':'REJECTED_BY_HUMAN'}
    return last_execution

@app.post('/api/execute',include_in_schema=False)
def execute(req: ExecuteRequest):
    global last_execution,effect_counter
    if current_receipt is None: raise HTTPException(409,'No decision receipt')
    amount=req.amount_usd if req.amount_usd is not None else ACTION.spend_usd
    recipient=req.recipient or ACTION.args['recipient']; tool=req.tool or ACTION.tool
    cand=Action(tool,{'recipient':recipient,'proposal_id':ACTION.args['proposal_id'],'amount_usd':amount},amount,True,True,recipient)
    tool_use_id=req.tool_use_id or TOOL_USE_ID
    def simulated_effect(idempotency_key: str):
        global effect_counter
        effect_counter += 1
        return {'external_effect':False,'simulated_effect_count':effect_counter,'idempotency_key_forwarded':idempotency_key}
    try:
        er=guard.execute(tool_use_id=tool_use_id,mandate=MANDATE,action=cand,receipt=current_receipt,effect=simulated_effect,truth='SIMULATED')
    except (PermissionError,ValueError,RuntimeError) as e:
        last_execution={'status':'BLOCKED','reason':str(e),'candidate_hash':cand.action_hash,'tool_use_id':tool_use_id}
        ledger.append('EXECUTION_BLOCKED',last_execution); raise HTTPException(409,last_execution)
    last_execution={**asdict(er),'execution_receipt_id':er.execution_receipt_id,'external_effect':False}
    ledger.append('EXECUTION_RECEIPT',last_execution)
    return last_execution

@app.post('/api/reset',include_in_schema=False)
def reset():
    global current_receipt,last_execution,effect_counter,authority,store,guard,ledger
    current_receipt=None; last_execution=None; effect_counter=0
    try: store.close()
    except Exception: pass
    authority=DecisionAuthority(); store=ExecutionStore(':memory:'); guard=ExactlyOnceResumeGuard(authority,store)
    ledger=EvidenceChain()
    for step in WORK: ledger.append('AUTO_WORK',{'step':step,'truth':'SIMULATED'})
    ledger.append('BOUNDARY',{'mode':boundary.mode,'reasons':boundary.reasons,'action_hash':boundary.action_hash,'mandate_hash':boundary.mandate_hash})
    return {'status':'RESET'}

# v0.9.6: Decision Inbox and official Strands runtime now share one canonical runtime path.
from afh.runtime_web_session import SESSION as RUNTIME_SESSION, RuntimeSessionError

@app.get('/api/runtime/state')
def runtime_state(): return RUNTIME_SESSION.state()

@app.post('/api/runtime/reset')
def runtime_reset(): return RUNTIME_SESSION.reset()

@app.post('/api/runtime/start')
def runtime_start():
    try: return RUNTIME_SESSION.start()
    except RuntimeSessionError as e: raise HTTPException(409,str(e))

class RuntimeResumeRequest(BaseModel): interrupt_id: str | None = None
@app.post('/api/runtime/approve-resume')
def runtime_approve_resume(req: RuntimeResumeRequest):
    try: return RUNTIME_SESSION.approve_resume(req.interrupt_id or RUNTIME_SESSION.state().get('interrupt_id'))
    except RuntimeSessionError as e: raise HTTPException(409,str(e))

@app.post('/api/runtime/deny-resume')
def runtime_deny_resume(req: RuntimeResumeRequest):
    try: return RUNTIME_SESSION.deny_resume(req.interrupt_id or RUNTIME_SESSION.state().get('interrupt_id'))
    except RuntimeSessionError as e: raise HTTPException(409,str(e))

@app.post('/api/runtime/replay')
def runtime_replay():
    try: return RUNTIME_SESSION.replay()
    except RuntimeSessionError as e: raise HTTPException(409,str(e))

@app.post('/api/runtime/tamper')
def runtime_tamper():
    try: return RUNTIME_SESSION.tamper()
    except RuntimeSessionError as e: raise HTTPException(409,str(e))
