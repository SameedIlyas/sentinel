"""PHI redaction and classification endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from policy_engine.auth.rbac import get_current_user
from policy_engine.database import get_db
from policy_engine.infrastructure.security.data_classifier import DataClassifier
from policy_engine.infrastructure.security.phi_redaction import (
    PHIRedactionEngine,
    RedactionStrategy,
)
from policy_engine.models.phi_log import DataClassificationRecord, PHIRedactionLog
from policy_engine.models.user import User, UserRole

router = APIRouter()
_engine = PHIRedactionEngine()
_classifier = DataClassifier()


class RedactRequest(BaseModel):
    text: str
    strategy: Optional[str] = RedactionStrategy.MASK


class ClassifyRequest(BaseModel):
    text: str


@router.post("/redact")
async def redact_phi(
    request: RedactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Redact PHI/PII from text and return de-identified content."""
    result = _engine.redact(request.text, strategy=request.strategy)

    # Log — NEVER store original text, only hash
    log = PHIRedactionLog(
        id=str(uuid.uuid4()),
        org_id=getattr(current_user, "organization_id", None),
        content_hash=PHIRedactionEngine.content_hash(request.text),
        phi_types_found=[f.phi_type for f in result.findings],
        strategy_used=request.strategy or RedactionStrategy.MASK,
        finding_count=len(result.findings),
        processed_at=datetime.utcnow(),
        user_id=current_user.id,
    )
    db.add(log)
    db.commit()

    return {
        "redacted_text": result.redacted_text,
        "finding_count": len(result.findings),
        "findings": [
            {
                "type": f.phi_type,
                "start": f.start,
                "end": f.end,
                "confidence": f.confidence,
            }
            for f in result.findings
        ],
        "processing_time_ms": result.processing_time_ms,
    }


@router.post("/classify")
async def classify_data(
    request: ClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Classify text sensitivity into one of 6 levels."""
    classification = _classifier.classify(request.text)

    rec = DataClassificationRecord(
        id=str(uuid.uuid4()),
        content_hash=PHIRedactionEngine.content_hash(request.text),
        classification_level=classification.level.value,
        confidence=str(classification.confidence),
        org_id=getattr(current_user, "organization_id", None),
        classified_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()

    return {
        "level": classification.level.value,
        "confidence": classification.confidence,
        "reasons": classification.reasons,
        "phi_finding_count": len(classification.phi_findings),
    }


@router.get("/redaction-log")
async def get_redaction_log(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List PHI redaction audit log entries (admin only)."""
    if current_user.role not in {UserRole.SYSTEM_ADMIN, UserRole.ORG_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    offset = (page - 1) * page_size
    logs = (
        db.query(PHIRedactionLog)
        .order_by(PHIRedactionLog.processed_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    total = db.query(PHIRedactionLog).count()

    return {
        "items": [
            {
                "id": log.id,
                "content_hash": log.content_hash,
                "phi_types": log.phi_types_found,
                "finding_count": log.finding_count,
                "processed_at": log.processed_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
