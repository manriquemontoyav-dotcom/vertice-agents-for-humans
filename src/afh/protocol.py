from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Iterable
import hashlib, hmac, json, secrets, time

def canonical(x: Any) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_obj(x: Any) -> str:
    return hashlib.sha256(canonical(x).encode()).hexdigest()

@dataclass(frozen=True)
class Mandate:
    objective: str
    max_spend_usd: float = 0.0
    may_represent_human: bool = False
    may_irreversible: bool = False
    scope: tuple[str, ...] = ()
    @property
    def mandate_hash(self) -> str:
        return sha256_obj(asdict(self))

@dataclass(frozen=True)
class Action:
    tool: str
    args: dict
    spend_usd: float = 0.0
    represents_human: bool = False
    irreversible: bool = False
    target: str = ""
    @property
    def action_hash(self) -> str:
        return sha256_obj(asdict(self))

@dataclass(frozen=True)
class Boundary:
    mode: str
    reasons: tuple[str, ...]
    action_hash: str
    mandate_hash: str

class BoundaryEngine:
    def evaluate(self, m: Mandate, a: Action) -> Boundary:
        reasons = []
        if a.spend_usd > m.max_spend_usd:
            reasons.append("spend_outside_mandate")
        if a.represents_human and not m.may_represent_human:
            reasons.append("human_representation")
        if a.irreversible and not m.may_irreversible:
            reasons.append("irreversible_effect")
        if m.scope and a.tool not in m.scope:
            reasons.append("tool_outside_scope")
        return Boundary("HUMAN" if reasons else "AUTO", tuple(reasons), a.action_hash, m.mandate_hash)

@dataclass(frozen=True)
class DecisionReceipt:
    action_hash: str
    mandate_hash: str
    decision: str
    nonce: str
    issued_at: int
    expires_at: int
    signature: str
    @property
    def receipt_id(self) -> str:
        return sha256_obj(asdict(self))

class DecisionAuthority:
    """Signs decisions but deliberately does not own execution idempotency."""
    def __init__(self, key: bytes | None = None):
        self.key = key or secrets.token_bytes(32)
    def _sign(self, body: dict) -> str:
        return hmac.new(self.key, canonical(body).encode(), hashlib.sha256).hexdigest()
    def _receipt(self, m: Mandate, a: Action, decision: str, ttl: int) -> DecisionReceipt:
        now = int(time.time())
        body = {"action_hash": a.action_hash, "mandate_hash": m.mandate_hash, "decision": decision,
                "nonce": secrets.token_hex(16), "issued_at": now, "expires_at": now + ttl}
        return DecisionReceipt(**body, signature=self._sign(body))
    def approve(self, m: Mandate, a: Action, ttl_seconds: int = 300) -> DecisionReceipt:
        return self._receipt(m, a, "approve", ttl_seconds)
    def reject(self, m: Mandate, a: Action, ttl_seconds: int = 300) -> DecisionReceipt:
        return self._receipt(m, a, "reject", ttl_seconds)
    def verify(self, r: DecisionReceipt, m: Mandate, a: Action, now: int | None = None):
        body = {"action_hash": r.action_hash, "mandate_hash": r.mandate_hash, "decision": r.decision,
                "nonce": r.nonce, "issued_at": r.issued_at, "expires_at": r.expires_at}
        now = int(time.time()) if now is None else now
        checks = [
            (hmac.compare_digest(r.signature, self._sign(body)), "invalid_signature"),
            (r.decision == "approve", "not_approved"),
            (r.action_hash == a.action_hash, "action_mutated"),
            (r.mandate_hash == m.mandate_hash, "mandate_changed"),
            (now <= r.expires_at, "receipt_expired"),
        ]
        for ok, reason in checks:
            if not ok: return False, reason
        return True, "authorized_exact_action"

class EvidenceChain:
    def __init__(self): self.rows = []
    def append(self, kind: str, payload: dict):
        prev = self.rows[-1]["hash"] if self.rows else "GENESIS"
        body = {"seq": len(self.rows)+1, "kind": kind, "payload": payload, "prev": prev}
        row = {**body, "hash": sha256_obj(body)}
        self.rows.append(row); return row
    @property
    def root(self) -> str:
        return self.rows[-1]["hash"] if self.rows else "GENESIS"
    def verify(self) -> bool:
        prev = "GENESIS"
        for row in self.rows:
            body = {k: row[k] for k in ("seq", "kind", "payload", "prev")}
            if row["prev"] != prev or sha256_obj(body) != row["hash"]: return False
            prev = row["hash"]
        return True

@dataclass(frozen=True)
class WorkflowStep:
    name: str
    action: Action

@dataclass(frozen=True)
class CompressionReport:
    total_steps: int
    auto_steps: int
    human_decisions: int
    compression_ratio: float | None
    boundaries: tuple[Boundary, ...]

class DecisionCompressionEngine:
    """Measures autonomy without suppressing real authority boundaries."""
    def analyze(self, mandate: Mandate, steps: Iterable[WorkflowStep]) -> CompressionReport:
        decisions=[]; total=0; auto=0
        engine=BoundaryEngine()
        for step in steps:
            total += 1
            b=engine.evaluate(mandate, step.action)
            if b.mode == "AUTO": auto += 1
            else: decisions.append(b)
        ratio = (auto / len(decisions)) if decisions else None
        return CompressionReport(total, auto, len(decisions), ratio, tuple(decisions))
