import sys, unittest, tempfile
from pathlib import Path
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
from afh.protocol import *
from afh.execution import *
from afh.demo_workflow import proposal_workflow
import webapp

class ProtocolTests(unittest.TestCase):
    def setUp(self): self.m=Mandate('prepare')
    def test_01_reversible_auto(self): self.assertEqual(BoundaryEngine().evaluate(self.m,Action('research',{})).mode,'AUTO')
    def test_02_spend_boundary(self): self.assertEqual(BoundaryEngine().evaluate(self.m,Action('submit',{},8750)).mode,'HUMAN')
    def test_03_representation_boundary(self): self.assertIn('human_representation',BoundaryEngine().evaluate(self.m,Action('send',{},represents_human=True)).reasons)
    def test_04_irreversible_boundary(self): self.assertIn('irreversible_effect',BoundaryEngine().evaluate(self.m,Action('publish',{},irreversible=True)).reasons)
    def test_05_scope_boundary(self): self.assertIn('tool_outside_scope',BoundaryEngine().evaluate(Mandate('x',scope=('search',)),Action('send',{})).reasons)
    def test_06_hash_canonical(self): self.assertEqual(Action('x',{'a':1,'b':2}).action_hash,Action('x',{'b':2,'a':1}).action_hash)
    def test_07_receipt_exact(self):
        a=Action('submit',{'amount':8750},8750,True,True); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); self.assertTrue(d.verify(r,self.m,a)[0])
    def test_08_amount_mutation(self):
        a=Action('submit',{'amount':8750},8750); b=Action('submit',{'amount':8751},8751); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); self.assertEqual(d.verify(r,self.m,b)[1],'action_mutated')
    def test_09_recipient_mutation(self):
        a=Action('send',{'to':'a'}); b=Action('send',{'to':'b'}); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); self.assertEqual(d.verify(r,self.m,b)[1],'action_mutated')
    def test_10_tool_substitution(self):
        a=Action('draft',{'id':1}); b=Action('publish',{'id':1}); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); self.assertEqual(d.verify(r,self.m,b)[1],'action_mutated')
    def test_11_signature_tamper(self):
        a=Action('submit',{}); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); bad=DecisionReceipt(r.action_hash,r.mandate_hash,r.decision,r.nonce,r.issued_at,r.expires_at,'0'*64); self.assertEqual(d.verify(bad,self.m,a)[1],'invalid_signature')
    def test_12_expiry(self):
        a=Action('submit',{}); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a,1); self.assertEqual(d.verify(r,self.m,a,r.expires_at+1)[1],'receipt_expired')
    def test_13_mandate_change(self):
        a=Action('submit',{}); d=DecisionAuthority(b'k'*32); r=d.approve(self.m,a); self.assertEqual(d.verify(r,Mandate('different'),a)[1],'mandate_changed')
    def test_14_reject_receipt(self):
        a=Action('submit',{}); d=DecisionAuthority(b'k'*32); r=d.reject(self.m,a); self.assertEqual(d.verify(r,self.m,a)[1],'not_approved')
    def test_15_ledger_valid(self):
        e=EvidenceChain(); e.append('work',{'x':1}); e.append('decision',{'y':2}); self.assertTrue(e.verify())
    def test_16_ledger_tamper(self):
        e=EvidenceChain(); e.append('work',{'x':1}); e.rows[0]['payload']['x']=2; self.assertFalse(e.verify())
    def test_17_pre_auth_spend(self): self.assertEqual(BoundaryEngine().evaluate(Mandate('buy',max_spend_usd=100),Action('buy',{},50)).mode,'AUTO')
    def test_18_pre_auth_identity(self): self.assertEqual(BoundaryEngine().evaluate(Mandate('send',may_represent_human=True),Action('send',{},represents_human=True)).mode,'AUTO')
    def test_19_pre_auth_irreversible(self): self.assertEqual(BoundaryEngine().evaluate(Mandate('publish',may_irreversible=True),Action('publish',{},irreversible=True)).mode,'AUTO')

class CompressionTests(unittest.TestCase):
    def test_20_demo_27_to_1(self):
        r=DecisionCompressionEngine().analyze(Mandate('prepare'),proposal_workflow()); self.assertEqual((r.total_steps,r.auto_steps,r.human_decisions),(27,26,1))
    def test_21_ratio_26(self): self.assertEqual(DecisionCompressionEngine().analyze(Mandate('prepare'),proposal_workflow()).compression_ratio,26)
    def test_22_no_boundary_ratio_none(self):
        r=DecisionCompressionEngine().analyze(Mandate('x'),[WorkflowStep('a',Action('work',{}))]); self.assertIsNone(r.compression_ratio)
    def test_23_two_real_decisions_preserved(self):
        s=[WorkflowStep('a',Action('send',{},represents_human=True)),WorkflowStep('b',Action('publish',{},irreversible=True))]; r=DecisionCompressionEngine().analyze(Mandate('x'),s); self.assertEqual(r.human_decisions,2)
    def test_24_scope_decision_not_suppressed(self):
        r=DecisionCompressionEngine().analyze(Mandate('x',scope=('search',)),[WorkflowStep('send',Action('send',{}))]); self.assertEqual(r.human_decisions,1)

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.m=Mandate('prepare'); self.a=Action('submit',{'amount':8750},8750,True,True); self.d=DecisionAuthority(b'k'*32); self.r=self.d.approve(self.m,self.a); self.store=ExecutionStore(':memory:'); self.g=ExactlyOnceResumeGuard(self.d,self.store); self.calls=0
    def eff(self,key): self.calls+=1; return {'n':self.calls,'key':key}
    def test_25_first_commit(self): self.assertEqual(self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff).status,'COMMITTED')
    def test_26_duplicate_resume_no_second_effect(self):
        x=self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff); y=self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff); self.assertEqual(self.calls,1); self.assertEqual(x.execution_receipt_id,y.execution_receipt_id)
    def test_27_idempotency_deterministic(self): self.assertEqual(derive_idempotency_key('t1',self.a),derive_idempotency_key('t1',self.a))
    def test_28_idempotency_changes_with_action(self): self.assertNotEqual(derive_idempotency_key('t1',self.a),derive_idempotency_key('t1',Action('submit',{'amount':8751},8751,True,True)))
    def test_29_tooluseid_required(self):
        with self.assertRaisesRegex(ValueError,'tool_use_id_required'): self.g.execute(tool_use_id='',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff)
    def test_30_tooluseid_action_substitution(self):
        self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff); b=Action('submit',{'amount':8751},8751,True,True); rb=self.d.approve(self.m,b)
        with self.assertRaisesRegex(PermissionError,'tool_use_id_action_substitution'): self.g.execute(tool_use_id='t1',mandate=self.m,action=b,receipt=rb,effect=self.eff)
    def test_31_tooluseid_receipt_substitution(self):
        self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff); r2=self.d.approve(self.m,self.a)
        with self.assertRaisesRegex(PermissionError,'tool_use_id_receipt_substitution'): self.g.execute(tool_use_id='t1',mandate=self.m,action=self.a,receipt=r2,effect=self.eff)
    def test_32_invalid_receipt_blocked_before_effect(self):
        b=Action('submit',{'amount':8751},8751,True,True)
        with self.assertRaisesRegex(PermissionError,'action_mutated'): self.g.execute(tool_use_id='t1',mandate=self.m,action=b,receipt=self.r,effect=self.eff)
        self.assertEqual(self.calls,0)
    def test_33_receipt_record_contains_tooluseid(self): self.assertEqual(self.g.execute(tool_use_id='abc',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff).tool_use_id,'abc')
    def test_34_receipt_truth_label(self): self.assertEqual(self.g.execute(tool_use_id='abc',mandate=self.m,action=self.a,receipt=self.r,effect=self.eff,truth='SIMULATED').truth,'SIMULATED')

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=TestClient(webapp.app)
    def setUp(self): self.c.post('/api/reset')
    def test_35_state_27_1(self):
        s=self.c.get('/api/state').json(); self.assertEqual((s['metrics']['total_steps'],s['metrics']['auto_steps'],s['metrics']['human_decisions']),(27,26,1))
    def test_36_exact_execute(self): self.c.post('/api/decision/approve'); self.assertEqual(self.c.post('/api/execute',json={}).status_code,200)
    def test_37_duplicate_api_resume_one_effect(self):
        self.c.post('/api/decision/approve'); a=self.c.post('/api/execute',json={}).json(); b=self.c.post('/api/execute',json={}).json(); self.assertEqual(a['execution_receipt_id'],b['execution_receipt_id']); self.assertEqual(b['effect_result']['simulated_effect_count'],1)
    def test_38_tamper_amount_blocked(self): self.c.post('/api/decision/approve'); self.assertEqual(self.c.post('/api/execute',json={'amount_usd':8751}).status_code,409)
    def test_39_tamper_recipient_blocked(self): self.c.post('/api/decision/approve'); self.assertEqual(self.c.post('/api/execute',json={'recipient':'Other Buyer'}).status_code,409)
    def test_40_tamper_tool_blocked(self): self.c.post('/api/decision/approve'); self.assertEqual(self.c.post('/api/execute',json={'tool':'publish_proposal'}).status_code,409)
    def test_41_no_receipt(self): self.assertEqual(self.c.post('/api/execute',json={}).status_code,409)
    def test_42_different_tooluseid_same_receipt_blocked(self):
        self.c.post('/api/decision/approve'); self.assertEqual(self.c.post('/api/execute',json={}).status_code,200); self.assertEqual(self.c.post('/api/execute',json={'tool_use_id':'tooluse_other'}).status_code,409)
    def test_43_ledger_valid(self): self.assertTrue(self.c.get('/api/state').json()['ledger_valid'])
    def test_44_receipt_has_idempotency_key(self): self.c.post('/api/decision/approve'); self.assertTrue(self.c.post('/api/execute',json={}).json()['idempotency_key'].startswith('afh_'))

if __name__=='__main__': unittest.main()
