# Final Release Runbook

1. Freeze one exact Git commit and build its deterministic source archive.
2. Run the full regression and publication/security scans from clean install.
3. Start one application process with official Strands Agents.
4. Produce `APPLICATION_E2E` evidence and require 17/17 or better.
5. Obtain a GREEN release result against the exact evidence bytes.
6. Execute browser E2E against that same application process.
7. Capture required screenshots and bind them into the demo-freeze result.
8. Record the video from the certified commit; keep it at most five minutes.
9. Assemble the sanitized candidate and require compliance 38/38.
10. Populate artifact SHA-256 values in the final manifest.
11. Run this gate at `candidate`; require 30/30.
12. After authorized publication, verify repository/video HTTP access and run
    `publication`; require 35/35.
13. Manuel reviews Devpost and confirms AWS Builder ID.
14. Record explicit authorization for the exact commit and candidate hash.
15. Run `submission`; require 42/42 before pressing Submit.

Never copy hashes or booleans from fixtures into real evidence.
