# Security scope

This repository is a hackathon demonstration. The consequential effect is simulated and no production credentials are required.

- Do not add real API keys, passwords, tokens, certificates, customer data, or production endpoints.
- Do not connect `submit_proposal` to a real external system without replacing the demo-only controls with a reviewed production design.
- The local constrained-resume guard is not a universal distributed exactly-once guarantee; external providers must honor idempotency semantics for that property to extend beyond this process.
