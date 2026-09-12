from typing import Any
from ..protocol import Action
from ..runtime_state import BROKER

TOOL_SPEC = {
    'name': 'submit_proposal',
    'description': 'Submit the exact prepared professional proposal. Consequential; AFH approval required.',
    'inputSchema': {
        'json': {
            'type': 'object',
            'properties': {
                'recipient': {'type': 'string'},
                'proposal_id': {'type': 'string'},
                'amount_usd': {'type': 'number'},
            },
            'required': ['recipient', 'proposal_id', 'amount_usd'],
        }
    },
}

def submit_proposal(tool_use: dict, **kwargs: Any) -> dict:
    tool_use_id = tool_use['toolUseId']
    data = tool_use['input']
    action = Action(
        tool='submit_proposal', args=data, spend_usd=float(data['amount_usd']),
        represents_human=True, irreversible=True, target=str(data['recipient'])
    )
    receipt = BROKER.execute(tool_use_id, action)
    return {
        'toolUseId': tool_use_id,
        'status': 'success',
        'content': [{'json': {
            'status': receipt.status,
            'truth': receipt.truth,
            'execution_receipt_id': receipt.execution_receipt_id,
            'effect_result': receipt.effect_result,
        }}],
    }
