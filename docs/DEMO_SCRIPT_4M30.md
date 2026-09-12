# VÉRTICE — 4:30 judge demo script

**0:00–0:25 — Problem.** “Agents are becoming capable enough to do real work. The hard question is no longer whether they can act; it is when they should return authority to a human.”

**0:25–0:45 — Product.** Introduce VÉRTICE: “The agent works. You decide.” State that reversible work proceeds autonomously while consequential commitments stop at a human decision boundary.

**0:45–1:35 — Live run.** Start the Strands agent. Show the workflow reaching `Confirm` and the Decision Inbox appearing from the real interrupt. Point to the exact amount, recipient, proposal, interrupt ID and frozen action digest.

**1:35–2:20 — Human decision and continuation.** Click Approve. Show the same runtime resume and one guarded simulated effect. Show `COMMITTED`, the execution receipt and `effect_count = 1`.

**2:20–2:55 — Proof, not promise.** Trigger replay: same receipt, no second effect. Trigger the US$8,751 mutation: blocked. Say explicitly that the external proposal submission is simulated; the Strands interrupt/resume path is real.

**2:55–3:35 — Why it matters.** Explain the target audience and the supervision-vs-authority tradeoff. Emphasize decision compression: humans should decide material commitments, not babysit every reversible step.

**3:35–4:05 — Technical differentiation.** Briefly show architecture. Do not claim HITL itself as novel. Focus on exact-action binding, constrained continuation, replay defense, mutation defense and evidence.

**4:05–4:30 — Close.** “More capable agents should not require surrendered human authority. VÉRTICE lets agents do the work while humans retain the decisions that matter.”
