# Testing VÉRTICE

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Full local regression

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Publication verification

```bash
python scripts/verify_publication.py
```

This checks the local regression and publication-safety requirements used by the candidate.

## Machine-readable regression result

```bash
python scripts/run_regression_json.py --output regression-result.json
```

## Public candidate compliance

```bash
python submission_compliance_gate.py . --output submission-compliance-result.json
```

A GREEN compliance result verifies repository structure, public documentation, security hygiene, required contribution disclosure, Strands dependency/import surface, and truth-label requirements. It does not replace runtime certification.

## REAL_STRANDS certification

The authoritative runtime certification is the GitHub Actions workflow:

`.github/workflows/application-e2e-release-gate.yml`

That workflow downloads the pinned `strands-agents==1.54.0` wheel, verifies its expected SHA-256, starts one application process, executes `application_e2e_certifier.py`, builds the release dossier, and requires a GREEN preflight release gate.

A fake-agent or local seam test must not be described as REAL_STRANDS evidence.

## Demo safety

The consequential external business effect is always **SIMULATED** for the hackathon candidate. Replay tests are labeled **REPLAY** and must produce no second effect.
