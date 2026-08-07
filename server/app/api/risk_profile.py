from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.repositories.risk_profile import RiskProfileRepository
from app.schemas.errors import ErrorResponse
from app.schemas.risk import (
    RiskProfileInput,
    RiskProfileRead,
    RiskProfileRecommendation,
    RiskProfileResponse,
    RiskRecommendationApply,
    RiskRecommendationApplyResponse,
    RiskRecommendationQuestions,
    RiskRecommendationRequest,
)
from app.services.risk_profile import RiskProfileService
from app.services.risk_recommendation import RiskRecommendationService

router = APIRouter(
    prefix="/api/v1/risk-profile",
    tags=["risk-profile"],
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
SessionDependency = Annotated[Session, Depends(get_session)]


def _service(session: Session) -> RiskProfileService:
    return RiskProfileService(RiskProfileRepository(session))


def _recommendation_service(session: Session) -> RiskRecommendationService:
    return RiskRecommendationService(session)


@router.get(
    "/recommendation",
    response_model=RiskProfileRecommendation,
)
def get_risk_recommendation(
    session: SessionDependency,
) -> RiskProfileRecommendation:
    return _recommendation_service(session).recommend()


@router.post(
    "/recommendation/refresh",
    response_model=RiskProfileRecommendation,
)
def refresh_risk_recommendation(
    payload: RiskRecommendationRequest,
    session: SessionDependency,
) -> RiskProfileRecommendation:
    return _recommendation_service(session).recommend(payload.answers)


@router.post(
    "/recommendation/apply",
    response_model=RiskRecommendationApplyResponse,
)
def apply_risk_recommendation(
    payload: RiskRecommendationApply,
    session: SessionDependency,
) -> RiskRecommendationApplyResponse:
    return _recommendation_service(session).apply(payload)


@router.get(
    "/recommendation/questions",
    response_model=RiskRecommendationQuestions,
)
def get_risk_recommendation_questions(
    session: SessionDependency,
) -> RiskRecommendationQuestions:
    return _recommendation_service(session).questions()


@router.get("", response_model=RiskProfileResponse)
def get_risk_profile(session: SessionDependency) -> RiskProfileResponse:
    profile = _service(session).get()
    if profile is None:
        return RiskProfileResponse(configured=False, profile=None)
    return RiskProfileResponse(
        configured=True,
        profile=RiskProfileRead.model_validate(profile),
    )


@router.put("", response_model=RiskProfileResponse)
def replace_risk_profile(
    payload: RiskProfileInput,
    session: SessionDependency,
) -> RiskProfileResponse:
    profile = _service(session).replace(payload)
    return RiskProfileResponse(
        configured=True,
        profile=RiskProfileRead.model_validate(profile),
    )
