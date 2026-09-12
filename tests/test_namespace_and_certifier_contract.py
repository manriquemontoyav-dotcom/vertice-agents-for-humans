import sys, unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'src'))

from fastapi.testclient import TestClient
import webapp
from afh.runtime_state import BROKER as STATE_BROKER
from afh.strands_runtime_harness import BROKER as HARNESS_BROKER
from afh.tools.submit_proposal import BROKER as TOOL_BROKER
from afh.runtime_web_session import BROKER as SESSION_BROKER

class CanonicalNamespaceContract(unittest.TestCase):
    def test_single_broker_identity(self):
        self.assertIs(STATE_BROKER,HARNESS_BROKER)
        self.assertIs(STATE_BROKER,TOOL_BROKER)
        self.assertIs(STATE_BROKER,SESSION_BROKER)

    def test_no_src_afh_runtime_modules_loaded(self):
        bad=[name for name in sys.modules if name=='src.afh' or name.startswith('src.afh.')]
        self.assertEqual(bad,[])

class ExternalResponseContract(unittest.TestCase):
    def test_ready_state_has_certifier_fields(self):
        c=TestClient(webapp.app)
        body=c.post('/api/runtime/reset').json()
        self.assertEqual(body['state'],'READY')
        self.assertEqual(body['external_effect'],'SIMULATED')
        self.assertIn('frozen_action',body)
        self.assertIn('exact_action_hash',body)

    def test_resume_request_can_omit_interrupt_id_at_schema_level(self):
        schema=TestClient(webapp.app).get('/openapi.json').json()
        req=schema['components']['schemas']['RuntimeResumeRequest']
        self.assertNotIn('interrupt_id',req.get('required',[]))

if __name__=='__main__': unittest.main()
