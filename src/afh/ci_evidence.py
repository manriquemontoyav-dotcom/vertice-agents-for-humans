from __future__ import annotations
from dataclasses import dataclass
from typing import Any

EXPECTED_STRANDS_VERSION = '1.54.0'
EXPECTED_WHEEL_SHA256 = 'ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c'

@dataclass(frozen=True)
class PassAssessment:
    passed: bool
    reasons: tuple[str, ...]

def assess(result: dict[str, Any], *, wheel_hash_verified: bool) -> PassAssessment:
    reasons=[]
    if not wheel_hash_verified: reasons.append('official_wheel_hash_not_verified')
    if result.get('strands_version') != EXPECTED_STRANDS_VERSION: reasons.append('wrong_strands_version')
    if result.get('status') != 'PASS': reasons.append('runtime_flow_not_pass')
    checks=result.get('checks') or {}
    for name in ('real_strands_version','interrupt_observed','resume_end_turn','execution_committed','single_effect','replay_same_receipt','mutation_blocked'):
        if checks.get(name) is not True: reasons.append(f'check_failed:{name}')
    truth=result.get('truth') or {}
    if truth.get('strands_runtime') != 'REAL': reasons.append('runtime_not_labeled_real')
    return PassAssessment(not reasons, tuple(reasons))
