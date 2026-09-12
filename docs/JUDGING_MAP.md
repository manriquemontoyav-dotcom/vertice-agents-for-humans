# VÉRTICE — judging map

This document maps the current prototype to the five equally weighted Stage Two criteria. It is a release checklist, not a marketing claim.

## 1. Technical Implementation
Judge-visible proof must use one path only:

`Strands Agent -> before_tool_call intervention -> Confirm -> interrupt -> Decision Inbox -> interruptResponse -> same Agent resumes -> guarded tool -> Execution Receipt`

Release evidence required: official Strands runtime/version, `stop_reason=interrupt`, exact interrupt ID, `end_turn` after resume, exactly one simulated consequential effect, replay returns the same receipt, and a post-authorization amount mutation is blocked.

## 2. Design
The Decision Inbox must make three things obvious in under ten seconds: what the agent already completed, why a human decision is required now, and exactly what will happen if approved. The UI must never call a parallel mock approval path.

## 3. Potential Impact
Target audience: people delegating consequential work to increasingly capable agents. Concrete problem: current agent systems force a tradeoff between frequent supervision and broad delegated authority. VÉRTICE demonstrates autonomous reversible work with human authority preserved at a material commitment.

## 4. Creativity & Originality
Do not claim that human-in-the-loop or Strands interrupts are novel. The differentiation hypothesis is narrower: exact authorization is bound to the proposed action and active mandate, continuation is constrained to the interrupted tool execution, and the resulting execution receipt is replay-safe and mutation-sensitive. Patentability is not asserted.

## 5. Presentation
The video must show, on the exact certified commit: autonomous work -> Strands interrupt -> visible exact-action decision -> human approval -> same runtime continuation -> one simulated effect -> receipt -> replay-safe proof -> US$8,751 mutation blocked. Keep architecture explanation subordinate to the live proof.
