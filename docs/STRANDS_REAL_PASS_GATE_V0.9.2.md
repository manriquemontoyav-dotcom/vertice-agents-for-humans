# Strands REAL PASS Gate — v0.9.2

PASS is intentionally strict. It requires all of the following in one evidence record:

1. Official PyPI wheel `strands-agents==1.54.0` downloaded on an Internet-connected runner.
2. Wheel SHA-256 equals PyPI-published `ca37b9001531596a634e9249f97fb03ce70997e216f6a71d4e8f8182818cbf5c`.
3. Actual installed distribution reports version `1.54.0`.
4. Actual `strands.Agent` executes the deterministic custom `Model`.
5. AFH `InterventionHandler.before_tool_call()` returns actual `Confirm`.
6. `AgentResult.stop_reason == "interrupt"` and an interrupt id exists.
7. `interruptResponse` resumes the real agent.
8. The module-based `submit_proposal` tool executes through AFH's guard.
9. Execution is `COMMITTED` and simulated effect count is exactly 1.
10. A replay returns the same execution receipt without a second effect.
11. A mutated US$8,751 action is blocked after US$8,750 approval.
12. Evidence JSON and logs are uploaded as a GitHub Actions artifact.

Truth labels:
- Strands runtime / interrupt / resume / tool invocation: REAL on green CI.
- Human approval: SIMULATED_PROGRAMMATIC in CI.
- External proposal submission: SIMULATED.
