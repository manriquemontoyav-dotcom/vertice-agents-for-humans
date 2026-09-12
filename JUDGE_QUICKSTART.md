# Judge Quickstart

Agents for Humans is a Strands-based prototype that demonstrates a constrained human-decision boundary around consequential agent actions.

## Fastest verification path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/verify_publication.py
python run_strands_real_pass.py
```

A successful Strands runtime gate must produce `STRANDS_REAL_PASS.json` with:

- `pass: true`
- Strands version `1.54.0`
- first stop reason `interrupt`
- final stop reason `end_turn`
- execution status `COMMITTED`
- `effect_count: 1`
- mutation blocked `true`

The external proposal effect is intentionally simulated. No buyer is contacted and no payment or irreversible external action occurs.

## Decision Inbox

```bash
uvicorn webapp:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## What to watch

The core demo compresses a professional workflow into one material human decision. The human approval is bound to the exact action and active mandate; mutation or replay is rejected by the execution guard.
