# Demo freeze runbook

1. Obtain GREEN from the application release pipeline on one exact commit.
2. Start that unchanged candidate and complete browser E2E on the same server.
3. Capture the five required states without exposing credentials or private material.
4. Hash every screenshot and preserve the browser evidence JSON unchanged.
5. Record the demo from the same commit and candidate.
6. Export the final video once; do not silently replace it afterward.
7. Record its SHA-256, duration, resolution and covered sections.
8. Run this gate and require 39/39 GREEN.
9. If the video changes, generate new metadata and rerun the entire gate.
10. Only after Manuel authorizes publication may the matching artifacts be uploaded.

Required screenshots:

- exact-action interruption before any effect;
- committed state with one receipt;
- replay blocked with the same receipt and no second effect;
- US$8,751 mutation blocked;
- denied action with zero effects.

Do not claim that automation verified the person's identity. The browser evidence
label remains `OBSERVED_UI_CLICK_UNVERIFIED_ACTOR`; the narrated human decision is an
observed event in the recorded demo.
