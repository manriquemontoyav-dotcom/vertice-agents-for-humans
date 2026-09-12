"""Actual Strands runtime harness for Agents for Humans v0.9.2.

Target: strands-agents==1.54.0.
The deterministic local Model removes cloud/model credentials from the proof.
A REAL PASS still requires the official Strands SDK runtime to be installed.
"""
from __future__ import annotations
import json, importlib
from typing import Any

from .protocol import Action, BoundaryEngine
from .runtime_state import BROKER

try:
    import strands
    from strands import Agent
    from strands.models import Model
    from strands.interventions import Confirm, InterventionHandler, Proceed
    STRANDS_AVAILABLE = True
    STRANDS_IMPORT_ERROR = None
except Exception as exc:
    STRANDS_AVAILABLE = False
    STRANDS_IMPORT_ERROR = repr(exc)
    Agent = None
    class Model: pass
    class InterventionHandler: pass

EXPECTED_STRANDS_VERSION = '1.54.0'
TOOL_USE_ID = 'afh-runtime-submit-001'

class DeterministicProposalModel(Model):
    """Offline deterministic Model used only for reproducible Strands E2E proof."""
    def __init__(self):
        self.config = {'model_id': 'afh-deterministic-proposal-v1'}

    def update_config(self, **model_config):
        self.config.update(model_config)

    def get_config(self):
        return dict(self.config)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        # Required abstract method in Strands 1.54.0 Model. Not used by this deterministic E2E proof.
        if False:
            yield {}
        raise NotImplementedError('structured_output_not_used_in_afh_runtime_proof')

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        has_tool_result = any(
            'toolResult' in block
            for message in messages
            for block in message.get('content', [])
        )
        yield {'messageStart': {'role': 'assistant'}}
        if not has_tool_result:
            payload = {
                'recipient': 'Demo Buyer',
                'proposal_id': 'AFH-DEMO-001',
                'amount_usd': 8750,
            }
            yield {'contentBlockStart': {
                'contentBlockIndex': 0,
                'start': {'toolUse': {
                    'name': 'submit_proposal',
                    'toolUseId': TOOL_USE_ID,
                }},
            }}
            yield {'contentBlockDelta': {
                'contentBlockIndex': 0,
                'delta': {'toolUse': {'input': json.dumps(payload, separators=(',', ':'))}},
            }}
            yield {'contentBlockStop': {'contentBlockIndex': 0}}
            yield {'messageStop': {'stopReason': 'tool_use'}}
        else:
            yield {'contentBlockDelta': {
                'contentBlockIndex': 0,
                'delta': {'text': 'Exact approved proposal completed.'},
            }}
            yield {'messageStop': {'stopReason': 'end_turn'}}

class AFHExactActionBoundary(InterventionHandler):
    name = 'afh-exact-action-boundary-v091'

    @property
    def on_error(self):
        # Official OnError accepts 'throw' | 'proceed' | 'deny'.
        return 'deny'

    def before_tool_call(self, event, **kwargs):
        if event.tool_use['name'] != 'submit_proposal':
            return Proceed()
        data = event.tool_use['input']
        action = Action(
            'submit_proposal', data, float(data['amount_usd']),
            True, True, str(data['recipient'])
        )
        boundary = BoundaryEngine().evaluate(BROKER.mandate, action)
        if boundary.mode == 'AUTO':
            return Proceed()
        BROKER.register_pending(event.tool_use['toolUseId'], action)
        return Confirm(prompt=(
            f"Authorize exact US${data['amount_usd']:,.0f} proposal to {data['recipient']}? "
            f"action={action.action_hash[:16]} mandate={BROKER.mandate.mandate_hash[:16]}"
        ))

def strands_version() -> str | None:
    if not STRANDS_AVAILABLE:
        return None
    try:
        from importlib.metadata import version
        return version('strands-agents')
    except Exception:
        return getattr(strands, '__version__', None)

def build_agent():
    if not STRANDS_AVAILABLE:
        raise RuntimeError(f'strands-agents is not installed/importable: {STRANDS_IMPORT_ERROR}')
    submit_tool = importlib.import_module('afh.tools.submit_proposal')
    return Agent(
        model=DeterministicProposalModel(),
        tools=[submit_tool],
        interventions=[AFHExactActionBoundary()],
        callback_handler=None,
    )

def run_verified_flow() -> dict[str, Any]:
    """Run official Strands Agent -> Confirm interrupt -> resume -> guarded tool effect."""
    BROKER.reset()
    if not STRANDS_AVAILABLE:
        return {
            'status': 'BLOCKED_ENVIRONMENT',
            'reason': 'strands-agents not installed/importable',
            'import_error': STRANDS_IMPORT_ERROR,
        }

    installed = strands_version()
    if installed != EXPECTED_STRANDS_VERSION:
        return {
            'status': 'FAIL_VERSION',
            'expected_strands_version': EXPECTED_STRANDS_VERSION,
            'strands_version': installed,
        }

    agent = build_agent()
    first = agent('Prepare and submit the verified proposal.')
    if first.stop_reason != 'interrupt' or not first.interrupts:
        return {
            'status': 'FAIL_NO_INTERRUPT',
            'strands_version': installed,
            'first_stop_reason': first.stop_reason,
            'interrupt_count': len(first.interrupts or []),
        }

    pending = BROKER.pending.get(TOOL_USE_ID)
    if pending is None:
        return {'status': 'FAIL_NO_PENDING_ACTION', 'strands_version': installed}

    # SIMULATED human action, but REAL Strands interrupt/resume semantics.
    BROKER.approve(TOOL_USE_ID)
    responses = [{
        'interruptResponse': {
            'interruptId': first.interrupts[0].id,
            'response': 'yes',
        }
    }]
    final = agent(responses)
    stored = BROKER.store.get(TOOL_USE_ID)

    # Read/replay the committed execution through AFH guard twice. Both calls must
    # return the same stored receipt and MUST NOT create another effect.
    first_receipt = BROKER.execute(TOOL_USE_ID, pending.action)
    replay_receipt = BROKER.execute(TOOL_USE_ID, pending.action)
    effect_count_after_replay = BROKER.effect_count

    # Mutation after approval: must fail closed.
    mutated = Action(
        'submit_proposal',
        {**pending.action.args, 'amount_usd': 8751},
        8751.0, True, True, pending.action.target
    )
    mutation_blocked = False
    mutation_reason = None
    try:
        BROKER.execute(TOOL_USE_ID, mutated)
    except Exception as exc:
        mutation_blocked = True
        mutation_reason = str(exc)

    checks = {
        'real_strands_version': installed == EXPECTED_STRANDS_VERSION,
        'interrupt_observed': first.stop_reason == 'interrupt' and bool(first.interrupts),
        'resume_end_turn': final.stop_reason == 'end_turn',
        'execution_committed': bool(stored and stored['status'] == 'COMMITTED'),
        'single_effect': effect_count_after_replay == 1,
        'replay_same_receipt': first_receipt.execution_receipt_id == replay_receipt.execution_receipt_id,
        'mutation_blocked': mutation_blocked,
    }
    status = 'PASS' if all(checks.values()) else 'FAIL'
    return {
        'status': status,
        'truth': {
            'strands_runtime': 'REAL',
            'human_approval': 'SIMULATED_PROGRAMMATIC',
            'external_effect': 'SIMULATED',
        },
        'strands_version': installed,
        'first_stop_reason': first.stop_reason,
        'final_stop_reason': final.stop_reason,
        'interrupt_count': len(first.interrupts),
        'tool_use_id': TOOL_USE_ID,
        'effect_count': effect_count_after_replay,
        'execution_status': stored['status'] if stored else None,
        'execution_truth': stored['truth'] if stored else None,
        'execution_receipt_id': replay_receipt.execution_receipt_id,
        'mutation_blocked': mutation_blocked,
        'mutation_reason': mutation_reason,
        'checks': checks,
    }
