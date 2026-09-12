from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from .protocol import Mandate, Action, DecisionAuthority, DecisionReceipt
from .execution import ExecutionStore, ExactlyOnceResumeGuard, ExecutionReceipt

@dataclass
class PendingDecision:
    tool_use_id: str
    action: Action

class RuntimeBroker:
    """In-memory demo broker. No network, no secrets persisted.

    The web/CLI decision surface issues a DecisionReceipt only after a human
    decision. Consequential tools must obtain that receipt from this broker and
    still pass the durable execution guard before an effect can occur.
    """
    def __init__(self):
        self.mandate = Mandate('Prepare and verify proposal; human retains submission authority.')
        self.authority = DecisionAuthority()
        self.store = ExecutionStore(':memory:')
        self.guard = ExactlyOnceResumeGuard(self.authority, self.store)
        self.pending: dict[str, PendingDecision] = {}
        self.approvals: dict[str, DecisionReceipt] = {}
        self.effect_count = 0

    def reset(self) -> None:
        self.pending.clear()
        self.approvals.clear()
        self.effect_count = 0
        self.store.clear()

    def register_pending(self, tool_use_id: str, action: Action) -> None:
        self.pending[tool_use_id] = PendingDecision(tool_use_id, action)

    def approve(self, tool_use_id: str) -> DecisionReceipt:
        p = self.pending[tool_use_id]
        receipt = self.authority.approve(self.mandate, p.action)
        self.approvals[tool_use_id] = receipt
        return receipt

    def execute(self, tool_use_id: str, action: Action) -> ExecutionReceipt:
        receipt = self.approvals.get(tool_use_id)
        if receipt is None:
            raise PermissionError('no_afh_decision_receipt')
        def effect(idempotency_key: str):
            self.effect_count += 1
            return {
                'provider_status': 'simulated_success',
                'idempotency_key': idempotency_key,
                'effect_sequence': self.effect_count,
            }
        return self.guard.execute(
            tool_use_id=tool_use_id, mandate=self.mandate, action=action,
            receipt=receipt, effect=effect, truth='SIMULATED'
        )

BROKER = RuntimeBroker()
