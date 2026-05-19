"""Prior Authorization domain logic — pure Python, CMS-0057-F compliant.

CRIT-005 — the verify_chain logic now consumes ``seq_no`` from each
record. The hash binds each row to its position in the per-org
sequence, so an attacker cannot delete the tail of the chain and
present the survivors as a clean chain — the seq_no gap surfaces.
"""
import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class PriorAuthDecision(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    PEND = "pend"


class FinalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"
    APPEALED = "appealed"


DENIAL_REASON_CODES: Dict[str, str] = {
    "001": "Not medically necessary",
    "002": "Experimental/investigational",
    "003": "Not covered benefit",
    "004": "Prior authorization not obtained",
    "005": "Documentation incomplete",
    "006": "Out of network",
    "007": "Duplicate claim",
    "008": "Benefit maximum reached",
}


@dataclass
class PriorAuthRecord:
    id: str
    patient_id_hash: str
    claim_id: str
    service_type: str
    request_date: str
    ai_recommendation: PriorAuthDecision
    final_decision: FinalDecision
    ai_confidence: float = 0.0
    human_reviewer_id: Optional[str] = None
    human_review_timestamp: Optional[str] = None
    denial_reason_code: Optional[str] = None
    ai_rationale: Optional[str] = None
    override_reason: Optional[str] = None
    prev_record_hash: str = ""
    record_hash: str = ""
    created_at: Optional[str] = None
    organization_id: Optional[str] = None
    seq_no: Optional[int] = None


def compute_record_hash(record_data: dict, prev_hash: str) -> str:
    """Compute SHA-256 hash of record content + prev_hash.

    record_data keys are sorted for determinism. Callers MUST include
    ``seq_no`` in ``record_data`` for CRIT-005 — its omission means the
    hash no longer binds the row to its sequence position and tail
    deletions become invisible again.
    """
    content = json.dumps({
        "prev_hash": prev_hash,
        **{k: str(record_data.get(k, "")) for k in sorted(record_data.keys())}
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def verify_chain(
    records: list,
    expected_count: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """Verify hash chain integrity and detect tail deletions.

    Args:
        records: list of ``{"id": str, "data": dict, "record_hash": str}``
                 ordered by ``seq_no`` (== ``created_at`` ASC for new
                 chains). ``data`` MUST include ``seq_no`` so the hash
                 binds the row to its position.
        expected_count: optional — the previously-recorded
                        ``total_records`` from PriorAuthChainStatus.
                        When supplied and greater than ``len(records)``,
                        the chain is reported invalid with reason
                        ``tail_deletion`` to surface CRIT-005.

    Returns:
        ``(True, None)`` if valid; otherwise ``(False, reason)`` where
        ``reason`` is the broken record id (middle deletion / tamper) or
        the literal ``"tail_deletion"`` (count regression).
    """
    if expected_count is not None and len(records) < expected_count:
        return False, "tail_deletion"

    # Gap detection in the seq_no sequence — if records are 1,2,3,5 then
    # row 4 was deleted from the tail of the contiguous prefix.
    seqs: list[int] = []
    for record in records:
        seq_val: Any = (record.get("data") or {}).get("seq_no")
        if isinstance(seq_val, (int, str)) and str(seq_val).isdigit():
            seqs.append(int(seq_val))
    if seqs:
        expected_seq = list(range(seqs[0], seqs[0] + len(seqs)))
        if seqs != expected_seq:
            return False, "seq_no_gap"

    prev_hash = ""
    for record in records:
        expected = compute_record_hash(record["data"], prev_hash)
        if record["record_hash"] != expected:
            return False, record["id"]
        prev_hash = record["record_hash"]
    return True, None
