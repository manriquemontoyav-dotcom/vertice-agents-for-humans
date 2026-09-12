from __future__ import annotations
from dataclasses import dataclass, asdict
from threading import RLock
from typing import Any
from .protocol import Action
from .runtime_state import BROKER
from .strands_runtime_harness import build_agent, strands_version, EXPECTED_STRANDS_VERSION, TOOL_USE_ID, STRANDS_AVAILABLE, STRANDS_IMPORT_ERROR

class RuntimeSessionError(RuntimeError): pass

@dataclass
class RuntimeView:
    phase: str='READY'; runtime: str='NOT_YET_RUN'; human_decision: str='NOT_YET_MADE'; external_effect: str='SIMULATED'
    interrupt_id: str|None=None; tool_use_id: str|None=None; action_hash: str|None=None; receipt_id: str|None=None
    effect_count: int=0; first_stop_reason: str|None=None; final_stop_reason: str|None=None; replay_result: str|None=None; tamper_result: str|None=None

class RealStrandsWebSession:
    """One canonical web session over the real Strands Agent interrupt/resume path."""
    def __init__(self): self.lock=RLock(); self.agent=None; self.pending_action=None; self.view=RuntimeView()
    def state(self):
        with self.lock:
            data=asdict(self.view)
            data['state']=self.view.phase
            if self.pending_action is not None:
                data['frozen_action']={
                    'proposal_id': self.pending_action.args.get('proposal_id'),
                    'amount': self.pending_action.args.get('amount_usd'),
                }
                data['exact_action_hash']=self.pending_action.action_hash
            else:
                data['frozen_action']=None
                data['exact_action_hash']=None
            data['external_effect']='SIMULATED'
            return data
    def reset(self):
        with self.lock:
            BROKER.reset(); self.agent=None; self.pending_action=None; self.view=RuntimeView(); return self.state()
    def start(self):
        with self.lock:
            if self.view.phase!='READY': raise RuntimeSessionError('start_requires_READY')
            if not STRANDS_AVAILABLE: raise RuntimeSessionError(f'strands_unavailable:{STRANDS_IMPORT_ERROR}')
            if strands_version()!=EXPECTED_STRANDS_VERSION: raise RuntimeSessionError(f'strands_version_mismatch:{strands_version()}')
            BROKER.reset(); self.agent=build_agent(); first=self.agent('Prepare and submit the verified proposal.')
            if first.stop_reason!='interrupt' or not first.interrupts: raise RuntimeSessionError(f'expected_interrupt_got:{first.stop_reason}')
            p=BROKER.pending.get(TOOL_USE_ID)
            if p is None: raise RuntimeSessionError('pending_action_missing')
            self.pending_action=p.action
            self.view=RuntimeView(phase='INTERRUPTED',runtime='REAL_STRANDS',human_decision='PENDING',interrupt_id=first.interrupts[0].id,tool_use_id=TOOL_USE_ID,action_hash=p.action.action_hash,effect_count=BROKER.effect_count,first_stop_reason=first.stop_reason)
            return self.state()
    def approve_resume(self, interrupt_id:str):
        with self.lock:
            if self.view.phase!='INTERRUPTED': raise RuntimeSessionError('approval_requires_INTERRUPTED')
            if interrupt_id!=self.view.interrupt_id: raise RuntimeSessionError('interrupt_id_mismatch')
            if self.agent is None or self.pending_action is None: raise RuntimeSessionError('runtime_session_missing')
            BROKER.approve(TOOL_USE_ID)
            final=self.agent([{'interruptResponse':{'interruptId':interrupt_id,'response':'yes'}}])
            stored=BROKER.store.get(TOOL_USE_ID)
            if final.stop_reason!='end_turn': raise RuntimeSessionError(f'expected_end_turn_got:{final.stop_reason}')
            if not stored or stored['status']!='COMMITTED' or BROKER.effect_count!=1: raise RuntimeSessionError('commit_invariant_failed')
            er=BROKER.execute(TOOL_USE_ID,self.pending_action)
            self.view=RuntimeView(phase='COMMITTED',runtime='REAL_STRANDS',human_decision='CLIENT_RESOLUTION_UNVERIFIED_ACTOR',interrupt_id=interrupt_id,tool_use_id=TOOL_USE_ID,action_hash=self.pending_action.action_hash,receipt_id=er.execution_receipt_id,effect_count=BROKER.effect_count,first_stop_reason='interrupt',final_stop_reason=final.stop_reason)
            return self.state()

    def deny_resume(self, interrupt_id:str):
        with self.lock:
            if self.view.phase!='INTERRUPTED': raise RuntimeSessionError('denial_requires_INTERRUPTED')
            if interrupt_id!=self.view.interrupt_id: raise RuntimeSessionError('interrupt_id_mismatch')
            if self.agent is None: raise RuntimeSessionError('runtime_session_missing')
            final=self.agent([{'interruptResponse':{'interruptId':interrupt_id,'response':'no'}}])
            if BROKER.effect_count!=0: raise RuntimeSessionError('deny_effect_invariant_failed')
            BROKER.pending.pop(TOOL_USE_ID, None)
            BROKER.approvals.pop(TOOL_USE_ID, None)
            self.view=RuntimeView(phase='DENIED',runtime='REAL_STRANDS',human_decision='CLIENT_DENIAL_UNVERIFIED_ACTOR',interrupt_id=interrupt_id,tool_use_id=TOOL_USE_ID,action_hash=self.pending_action.action_hash if self.pending_action else None,effect_count=0,first_stop_reason='interrupt',final_stop_reason=getattr(final,'stop_reason',None))
            return self.state()
    def replay(self):
        with self.lock:
            if self.view.phase!='COMMITTED' or self.pending_action is None: raise RuntimeSessionError('replay_requires_COMMITTED')
            er=BROKER.execute(TOOL_USE_ID,self.pending_action)
            if BROKER.effect_count!=1 or er.execution_receipt_id!=self.view.receipt_id: raise RuntimeSessionError('replay_invariant_failed')
            self.view.replay_result='SAME_RECEIPT_NO_SECOND_EFFECT'; self.view.effect_count=BROKER.effect_count; return self.state()
    def tamper(self):
        with self.lock:
            if self.view.phase!='COMMITTED' or self.pending_action is None: raise RuntimeSessionError('tamper_requires_COMMITTED')
            a=self.pending_action
            mutated=Action(a.tool,{**a.args,'amount_usd':8751},8751.0,a.represents_human,a.irreversible,a.target)
            try: BROKER.execute(TOOL_USE_ID,mutated)
            except Exception as exc:
                if BROKER.effect_count!=1: raise RuntimeSessionError('tamper_changed_effect_count')
                self.view.tamper_result=f'BLOCKED_8751:{exc}'; return self.state()
            raise RuntimeSessionError('tamper_was_not_blocked')

SESSION=RealStrandsWebSession()
