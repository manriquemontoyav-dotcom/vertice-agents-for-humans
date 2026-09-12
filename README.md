# VÉRTICE — Agents for Humans

> **The agent works. You decide.**

VÉRTICE is an authorization architecture for consequential agent actions, built for **Agents for Humans** with the **Strands Agents SDK** integration path.

## Problem

Useful agents need room to work autonomously, but consequential actions create an authority problem. Interrupting a person for every step destroys autonomy; granting broad authority makes it hard to prove what a person actually approved. VÉRTICE lets the agent perform reversible preparation, then stops at the exact action that requires human authority.

## Audience

VÉRTICE is designed for professionals and teams that want agentic automation for meaningful work while retaining explicit human authority over consequential external actions such as submissions, commitments, approvals, or transactions.

## Why it matters

The product goal is to preserve useful agent autonomy without turning a human approval into a blanket permission. The decision is bound to the exact consequential action, and the continuation is constrained so that a consumed authorization cannot be silently replayed or mutated into a different action.

## Features

- Autonomous reversible preparation before the authority boundary.
- Strands `before_tool_call` intervention path with `Confirm` and interrupt/resume semantics.
- Decision Inbox for the runtime-issued action requiring human resolution.
- Exact-action binding to consequential parameters and runtime decision context.
- Single-consumption continuation guard.
- Replay defense: a previously consumed authorization cannot create a second effect.
- Mutation defense: the canonical US$8,750 demo authorization cannot be reused for US$8,751.
- Evidence and receipt path connecting decision, continuation, and effect.
- Fail-closed release, demo-freeze, and submission gates.

## Architecture

The canonical flow is:

`agent work → authority boundary → exact decision → human resolution → constrained continuation → simulated effect → evidence`

The browser does not set `COMMITTED` and cannot execute the consequential effect directly. Runtime state and authorization consumption are server controlled. See `docs/ARCHITECTURE.md` and `docs/architecture.svg`.

## Truth labels

- **REAL LOCAL:** boundary logic, decision receipts, constrained resume guard, Decision Inbox, automated tests, replay/mutation defenses, and local release checks actually executed on the candidate.
- **SIMULATED:** the external business effect. The demo never contacts a real buyer, payment rail, or external submission endpoint.
- **REPLAY:** a deliberate attempt to reuse an already consumed authorization/receipt; the expected outcome is no second effect.
- **REAL_STRANDS:** reserved for evidence produced by an execution using the official Strands SDK. A local unit/fake-agent pass is not labeled REAL_STRANDS.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The release workflow additionally verifies the pinned `strands-agents==1.54.0` wheel SHA-256 before executing the runtime certification path.

## Running

Start the application:

```bash
uvicorn webapp:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

The browser UI uses the canonical `/api/runtime/*` route family. Legacy simulated demo endpoints are hidden from OpenAPI and are not used by the UI.

For the Strands integration path:

```bash
python preflight.py
python run_strands_demo.py
```

The intended runtime sequence is `interrupt → human decision response → resume → guarded SIMULATED effect → end_turn`.

## Testing

Run the publication-safe regression path:

```bash
python scripts/verify_publication.py
```

Run the machine-readable regression runner:

```bash
python scripts/run_regression_json.py --output regression-result.json
```

Run the public candidate compliance gate:

```bash
python submission_compliance_gate.py . --output submission-compliance-result.json
```

A REAL_STRANDS release candidate must also pass `.github/workflows/application-e2e-release-gate.yml` on the exact Git commit used for evidence.

## Technical differentiation

Strands interventions, `Confirm`, and interrupts are platform primitives and are not claimed as VÉRTICE inventions. The differentiation hypothesis is the composition of exact-action authorization, runtime-bound decision context, constrained continuation, single-consumption authority, replay/mutation resistance, and effect provenance.

## Safety and privacy

The repository contains no production credentials and performs no real external consequential action. Evidence should avoid raw prompts, secrets, and unnecessary personal data. See `SECURITY.md`.

## Human and AI contributions

See `docs/CONTRIBUTIONS_AND_AI.md` for the contribution record and pre-existing-work disclosure.

## Judge quickstart

See `JUDGE_QUICKSTART.md` for the shortest reproducible inspection path and `docs/JUDGING_MAP.md` for criterion-to-evidence mapping.

## License

MIT. See `LICENSE`.
