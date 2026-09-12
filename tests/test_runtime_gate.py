import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from afh.runtime_state import RuntimeBroker
from afh.ci_evidence import assess, EXPECTED_STRANDS_VERSION, EXPECTED_WHEEL_SHA256
from afh.strands_runtime_harness import DeterministicProposalModel

class RuntimeGateTests(unittest.TestCase):
    def test_broker_reset(self):
        b=RuntimeBroker(); b.effect_count=2; b.pending['x']=object(); b.approvals['x']=object(); b.reset()
        self.assertEqual(b.effect_count,0); self.assertFalse(b.pending); self.assertFalse(b.approvals)
    def test_expected_official_wheel_hash(self):
        self.assertEqual(EXPECTED_WHEEL_SHA256,'ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c')
    def test_model_exposes_required_methods(self):
        self.assertTrue(callable(getattr(DeterministicProposalModel,'stream',None)))
        self.assertTrue(callable(getattr(DeterministicProposalModel,'update_config',None)))
        self.assertTrue(callable(getattr(DeterministicProposalModel,'get_config',None)))
        self.assertTrue(callable(getattr(DeterministicProposalModel,'structured_output',None)))
    def test_assessment_requires_strict_runtime_checks(self):
        checks={k:True for k in ('real_strands_version','interrupt_observed','resume_end_turn','execution_committed','single_effect','replay_same_receipt','mutation_blocked')}
        result={'status':'PASS','strands_version':EXPECTED_STRANDS_VERSION,'truth':{'strands_runtime':'REAL'},'checks':checks}
        self.assertTrue(assess(result,wheel_hash_verified=True).passed)
        self.assertFalse(assess(result,wheel_hash_verified=False).passed)

if __name__=='__main__': unittest.main()
