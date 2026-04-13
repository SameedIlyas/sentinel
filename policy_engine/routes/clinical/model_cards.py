"""Model Card CRUD + lifecycle endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from policy_engine.database import get_db
from policy_engine.auth.rbac import get_current_user
from policy_engine.models.user import User, has_permission
from policy_engine.models.model_card import ModelCard, ModelCardVersion
from policy_engine.domain.clinical.model_card import LifecycleStage, ModelCardEntity
from policy_engine.config import settings
from policy_engine.services.github_integration import GitHubIntegrationService
from policy_engine.services.mlflow_integration import MLflowIntegrationService
from policy_engine.services.model_card_service import (
    ModelCardAutoFillRequest,
    ModelCardAutoFillResult,
    ModelCardAutoFillService,
)
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ModelCardCreate(BaseModel):
    name: str
    version: str = "1.0"
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: Optional[dict] = None
    bias_summary: Optional[dict] = None
    fda_status: Optional[str] = None
    chai_version: str = "1.0"
    organization_id: Optional[str] = None


class ModelCardUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: Optional[dict] = None
    bias_summary: Optional[dict] = None
    fda_status: Optional[str] = None


class ModelCardResponse(BaseModel):
    id: str
    name: str
    version: str
    lifecycle_stage: str
    intended_use: Optional[str] = None
    clinical_indications: Optional[str] = None
    contraindications: Optional[str] = None
    training_data_source: Optional[str] = None
    performance_metrics: dict = {}
    bias_summary: dict = {}
    fda_status: Optional[str] = None
    chai_version: str
    organization_id: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_permission(current_user: User, action: str) -> None:
    if not has_permission(current_user.role, "model_cards", action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to {action} model_cards",
        )


def _get_card_or_404(card_id: str, db: Session) -> ModelCard:
    card = db.query(ModelCard).filter(ModelCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model card not found")
    return card


def _to_response(card: ModelCard) -> dict:
    return {
        "id": card.id,
        "name": card.name,
        "version": card.version,
        "lifecycle_stage": card.lifecycle_stage,
        "intended_use": card.intended_use,
        "clinical_indications": card.clinical_indications,
        "contraindications": card.contraindications,
        "training_data_source": card.training_data_source,
        "performance_metrics": card.performance_metrics or {},
        "bias_summary": card.bias_summary or {},
        "fda_status": card.fda_status,
        "chai_version": card.chai_version,
        "organization_id": card.organization_id,
        "created_by": card.created_by,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/model-cards", response_model=List[ModelCardResponse])
def list_model_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    cards = db.query(ModelCard).all()
    return [_to_response(c) for c in cards]


@router.post("/model-cards", status_code=status.HTTP_201_CREATED)
def create_model_card(
    payload: ModelCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "create")
    now = datetime.utcnow()
    card = ModelCard(
        id=str(uuid.uuid4()),
        name=payload.name,
        version=payload.version,
        lifecycle_stage="draft",
        intended_use=payload.intended_use,
        clinical_indications=payload.clinical_indications,
        contraindications=payload.contraindications,
        training_data_source=payload.training_data_source,
        performance_metrics=payload.performance_metrics or {},
        bias_summary=payload.bias_summary or {},
        fda_status=payload.fda_status,
        chai_version=payload.chai_version,
        organization_id=payload.organization_id,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.get("/model-cards/{card_id}")
def get_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return _to_response(card)


@router.put("/model-cards/{card_id}")
def update_model_card(
    card_id: str,
    payload: ModelCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    if card.lifecycle_stage not in ("draft", "review"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT or REVIEW cards can be updated",
        )

    update_data = payload.dict(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(card, field_name, value)
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.post("/model-cards/{card_id}/review")
def submit_for_review(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition DRAFT -> REVIEW."""
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.REVIEW)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.post("/model-cards/{card_id}/publish")
def publish_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition REVIEW -> PUBLISHED and create a version snapshot."""
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.PUBLISHED)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()

    # Create version snapshot
    version_record = ModelCardVersion(
        id=str(uuid.uuid4()),
        model_card_id=card.id,
        version_number=card.version,
        content={
            "name": card.name,
            "lifecycle_stage": card.lifecycle_stage,
            "performance_metrics": card.performance_metrics,
            "bias_summary": card.bias_summary,
        },
        published_by=current_user.id,
        published_at=datetime.utcnow(),
    )
    db.add(version_record)
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.post("/model-cards/{card_id}/retire")
def retire_model_card(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition PUBLISHED -> RETIRED."""
    _check_permission(current_user, "update")
    card = _get_card_or_404(card_id, db)

    entity = ModelCardEntity(id=card.id, name=card.name, lifecycle_stage=LifecycleStage(card.lifecycle_stage))
    try:
        entity.transition_to(LifecycleStage.RETIRED)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    card.lifecycle_stage = entity.lifecycle_stage.value
    card.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(card)
    return _to_response(card)


@router.get("/model-cards/{card_id}/export-summary")
def export_summary(
    card_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return structured JSON summary of the model card."""
    _check_permission(current_user, "read")
    card = _get_card_or_404(card_id, db)
    return {
        "id": card.id,
        "name": card.name,
        "version": card.version,
        "lifecycle_stage": card.lifecycle_stage,
        "intended_use": card.intended_use,
        "fda_status": card.fda_status,
        "chai_version": card.chai_version,
        "performance_metrics": card.performance_metrics or {},
        "bias_summary": card.bias_summary or {},
        "export_timestamp": datetime.utcnow().isoformat(),
    }


@router.post(
    "/model-cards/{card_id}/auto-fill",
    response_model=ModelCardAutoFillResult,
    status_code=status.HTTP_200_OK,
)
async def auto_fill_model_card(
    card_id: str,
    payload: ModelCardAutoFillRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-populate CHAI model card sections from GitHub + MLflow."""
    _check_permission(current_user, "update")
    _get_card_or_404(card_id, db)

    github_svc = GitHubIntegrationService(
        token=settings.GITHUB_TOKEN,
        base_url=settings.GITHUB_API_BASE_URL,
        timeout_seconds=settings.GITHUB_REQUEST_TIMEOUT_SECONDS,
    )
    mlflow_svc = MLflowIntegrationService(
        tracking_uri=settings.MLFLOW_TRACKING_URI,
        timeout_seconds=settings.MLFLOW_REQUEST_TIMEOUT_SECONDS,
    )
    service = ModelCardAutoFillService(
        github_service=github_svc,
        mlflow_service=mlflow_svc,
    )

    try:
        return await service.auto_fill(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
