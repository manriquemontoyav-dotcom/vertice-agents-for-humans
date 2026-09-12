from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable
import hashlib, json, sqlite3, time
from .protocol import Action, Mandate, DecisionReceipt, DecisionAuthority, canonical, sha256_obj

@dataclass(frozen=True)
class ExecutionReceipt:
    tool_use_id: str
    idempotency_key: str
    action_hash: str
    mandate_hash: str
    decision_receipt_id: str
    status: str
    effect_result: dict
    committed_at: int
    truth: str
    @property
    def execution_receipt_id(self) -> str:
        return sha256_obj(asdict(self))

def derive_idempotency_key(tool_use_id: str, action: Action) -> str:
    # Provider-safe deterministic key. Different action => different key.
    material = {"tool_use_id": tool_use_id, "action_hash": action.action_hash}
    return "afh_" + hashlib.sha256(canonical(material).encode()).hexdigest()

class ExecutionStore:
    def __init__(self, path: str = ':memory:'):
        self.path=path
        self.conn=sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute("""CREATE TABLE IF NOT EXISTS executions (
            tool_use_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            action_hash TEXT NOT NULL,
            mandate_hash TEXT NOT NULL,
            decision_receipt_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            effect_result TEXT,
            committed_at INTEGER,
            truth TEXT NOT NULL
        )""")
    def clear(self): self.conn.execute('DELETE FROM executions')
    def close(self):
        conn=getattr(self,'conn',None)
        if conn is not None:
            try: conn.close()
            finally: self.conn=None
    def __del__(self):
        try: self.close()
        except Exception: pass
    def get(self, tool_use_id: str):
        row=self.conn.execute('SELECT * FROM executions WHERE tool_use_id=?',(tool_use_id,)).fetchone()
        if not row: return None
        return dict(row)

class ExactlyOnceResumeGuard:
    """Local durable guard for resumed consequential tool calls.

    Guarantees that the same Strands toolUseId cannot produce a second AFH effect
    through this guard after COMMIT. True distributed exactly-once behavior still
    requires the external provider to honor the supplied idempotency key.
    """
    def __init__(self, authority: DecisionAuthority, store: ExecutionStore):
        self.authority=authority; self.store=store

    def execute(self, *, tool_use_id: str, mandate: Mandate, action: Action,
                receipt: DecisionReceipt, effect: Callable[[str], dict], truth='SIMULATED') -> ExecutionReceipt:
        if not tool_use_id: raise ValueError('tool_use_id_required')
        ok, reason=self.authority.verify(receipt, mandate, action)
        if not ok: raise PermissionError(reason)
        key=derive_idempotency_key(tool_use_id, action)
        rid=receipt.receipt_id
        cur=self.store.conn.cursor()
        try:
            cur.execute('BEGIN IMMEDIATE')
            prior=cur.execute('SELECT * FROM executions WHERE tool_use_id=?',(tool_use_id,)).fetchone()
            if prior:
                prior=dict(prior)
                if prior['action_hash'] != action.action_hash: raise PermissionError('tool_use_id_action_substitution')
                if prior['decision_receipt_id'] != rid: raise PermissionError('tool_use_id_receipt_substitution')
                if prior['status']=='COMMITTED':
                    cur.execute('COMMIT')
                    return self._from_row(prior)
                raise RuntimeError('execution_in_progress')
            try:
                cur.execute("""INSERT INTO executions(tool_use_id,idempotency_key,action_hash,mandate_hash,
                    decision_receipt_id,status,effect_result,committed_at,truth) VALUES(?,?,?,?,?,'PENDING',NULL,NULL,?)""",
                    (tool_use_id,key,action.action_hash,mandate.mandate_hash,rid,truth))
            except sqlite3.IntegrityError as e:
                if 'decision_receipt_id' in str(e):
                    raise PermissionError('decision_receipt_reuse') from e
                if 'idempotency_key' in str(e):
                    raise PermissionError('idempotency_key_collision') from e
                raise
            cur.execute('COMMIT')
        except Exception:
            try: cur.execute('ROLLBACK')
            except Exception: pass
            raise

        # Effect adapter receives the same deterministic idempotency key. In real
        # integrations this key MUST be forwarded to a provider that supports it.
        result=effect(key)
        committed=int(time.time())
        cur=self.store.conn.cursor()
        cur.execute('BEGIN IMMEDIATE')
        cur.execute("UPDATE executions SET status='COMMITTED', effect_result=?, committed_at=? WHERE tool_use_id=? AND status='PENDING'",
                    (json.dumps(result,sort_keys=True),committed,tool_use_id))
        if cur.rowcount != 1:
            cur.execute('ROLLBACK'); raise RuntimeError('commit_state_lost')
        row=cur.execute('SELECT * FROM executions WHERE tool_use_id=?',(tool_use_id,)).fetchone()
        cur.execute('COMMIT')
        return self._from_row(dict(row))

    @staticmethod
    def _from_row(row: dict) -> ExecutionReceipt:
        return ExecutionReceipt(
            tool_use_id=row['tool_use_id'], idempotency_key=row['idempotency_key'],
            action_hash=row['action_hash'], mandate_hash=row['mandate_hash'],
            decision_receipt_id=row['decision_receipt_id'], status=row['status'],
            effect_result=json.loads(row['effect_result']) if row['effect_result'] else {},
            committed_at=row['committed_at'] or 0, truth=row['truth'])
