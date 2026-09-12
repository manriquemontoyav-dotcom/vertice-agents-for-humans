import sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))
from fastapi.testclient import TestClient
import webapp
from afh import runtime_web_session as rws

class RuntimeWebApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c=TestClient(webapp.app)
    def setUp(self): self.c.post('/api/runtime/reset')
    def test_state_ready(self): self.assertEqual(self.c.get('/api/runtime/state').json()['phase'],'READY')
    def test_out_of_order_replay_409(self): self.assertEqual(self.c.post('/api/runtime/replay').status_code,409)
    def test_start_fail_closed_without_sdk_or_real_interrupt(self):
        r=self.c.post('/api/runtime/start')
        if not rws.STRANDS_AVAILABLE: self.assertEqual(r.status_code,409)
        else: self.assertIn(r.status_code,(200,409))
    def test_wrong_interrupt_rejected_without_resume(self):
        if not rws.STRANDS_AVAILABLE: self.skipTest('official Strands SDK unavailable in local runner')
        s=self.c.post('/api/runtime/start')
        if s.status_code!=200: self.skipTest(s.text)
        self.assertEqual(self.c.post('/api/runtime/approve-resume',json={'interrupt_id':'wrong'}).status_code,409)

class RuntimeSessionWithFakeAgent(unittest.TestCase):
    def test_session_contract_without_claiming_real_strands(self):
        # Unit-level seam test only. It proves UI/session wiring, NOT SDK behavior.
        class I: id='int-1'
        class R:
            def __init__(self,stop): self.stop_reason=stop; self.interrupts=[I()] if stop=='interrupt' else []
        class A:
            def __call__(self,x):
                if isinstance(x,str):
                    from afh.protocol import Action
                    rws.BROKER.register_pending(rws.TOOL_USE_ID,Action('submit_proposal',{'recipient':'Demo Buyer','proposal_id':'AFH-DEMO-001','amount_usd':8750},8750,True,True,'Demo Buyer'))
                    return R('interrupt')
                p=rws.BROKER.pending[rws.TOOL_USE_ID]; rws.BROKER.execute(rws.TOOL_USE_ID,p.action); return R('end_turn')
        old_avail,old_build,old_ver=rws.STRANDS_AVAILABLE,rws.build_agent,rws.strands_version
        try:
            rws.STRANDS_AVAILABLE=True; rws.build_agent=lambda:A(); rws.strands_version=lambda:rws.EXPECTED_STRANDS_VERSION
            s=rws.RealStrandsWebSession(); a=s.start(); self.assertEqual(a['phase'],'INTERRUPTED')
            c=s.approve_resume(a['interrupt_id']); self.assertEqual((c['phase'],c['effect_count']),('COMMITTED',1))
            self.assertEqual(s.replay()['effect_count'],1); self.assertTrue(s.tamper()['tamper_result'].startswith('BLOCKED_8751'))
        finally: rws.STRANDS_AVAILABLE=old_avail; rws.build_agent=old_build; rws.strands_version=old_ver; rws.BROKER.reset()

class RuntimeUiSinglePathContract(unittest.TestCase):
    def test_ui_uses_runtime_routes_not_legacy_demo_routes(self):
        html=(Path(__file__).parents[1]/'static'/'index.html').read_text()
        self.assertIn('/api/runtime/start',html)
        self.assertIn('/api/runtime/approve-resume',html)
        self.assertIn('/api/runtime/deny-resume',html)
        self.assertNotIn("fetch('/api/decision/approve'",html)
        self.assertNotIn("fetch('/api/execute'",html)
        self.assertIn('VÉRTICE',html)

    def test_legacy_routes_hidden_from_openapi(self):
        c=TestClient(webapp.app)
        paths=c.get('/openapi.json').json()['paths']
        self.assertNotIn('/api/decision/approve',paths)
        self.assertNotIn('/api/execute',paths)
        self.assertIn('/api/runtime/start',paths)

class RuntimeConcurrencyAndDenialContract(unittest.TestCase):
    """Unit-level seam tests. They do not claim official Strands SDK execution."""
    @staticmethod
    def _fake_agent():
        class I: id='int-concurrent-1'
        class R:
            def __init__(self, stop):
                self.stop_reason=stop
                self.interrupts=[I()] if stop=='interrupt' else []
        class A:
            def __call__(self, x):
                if isinstance(x, str):
                    from afh.protocol import Action
                    rws.BROKER.register_pending(
                        rws.TOOL_USE_ID,
                        Action('submit_proposal', {'recipient':'Demo Buyer','proposal_id':'AFH-DEMO-001','amount_usd':8750},8750,True,True,'Demo Buyer')
                    )
                    return R('interrupt')
                response=x[0]['interruptResponse']['response']
                if response=='yes':
                    p=rws.BROKER.pending[rws.TOOL_USE_ID]
                    rws.BROKER.execute(rws.TOOL_USE_ID,p.action)
                return R('end_turn')
        return A()

    def _install_fake(self):
        old=(rws.STRANDS_AVAILABLE,rws.build_agent,rws.strands_version)
        rws.STRANDS_AVAILABLE=True
        rws.build_agent=lambda:self._fake_agent()
        rws.strands_version=lambda:rws.EXPECTED_STRANDS_VERSION
        return old

    def _restore(self, old):
        rws.STRANDS_AVAILABLE,rws.build_agent,rws.strands_version=old
        rws.BROKER.reset()

    def test_concurrent_approvals_at_most_one_effect(self):
        from concurrent.futures import ThreadPoolExecutor
        old=self._install_fake()
        try:
            s=rws.RealStrandsWebSession()
            started=s.start()
            iid=started['interrupt_id']
            def attempt():
                try:
                    out=s.approve_resume(iid)
                    return ('OK',out['effect_count'])
                except rws.RuntimeSessionError as exc:
                    return ('BLOCKED',str(exc))
            with ThreadPoolExecutor(max_workers=2) as ex:
                results=list(ex.map(lambda _: attempt(), range(2)))
            self.assertEqual(sum(1 for kind,_ in results if kind=='OK'),1)
            self.assertEqual(rws.BROKER.effect_count,1)
            self.assertEqual(s.state()['phase'],'COMMITTED')
        finally:
            self._restore(old)

    def test_denial_terminal_zero_effect(self):
        old=self._install_fake()
        try:
            s=rws.RealStrandsWebSession()
            started=s.start()
            denied=s.deny_resume(started['interrupt_id'])
            self.assertEqual(denied['phase'],'DENIED')
            self.assertEqual(denied['effect_count'],0)
            self.assertEqual(rws.BROKER.effect_count,0)
            with self.assertRaises(rws.RuntimeSessionError):
                s.approve_resume(started['interrupt_id'])
        finally:
            self._restore(old)
