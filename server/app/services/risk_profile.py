from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.core.errors import risk_profile_validation
from app.models.database import RiskProfileRecord, RiskProfileSource
from app.repositories.risk_profile import RiskProfileRepository
from app.schemas.risk import RiskProfileInput


class RiskProfileService:
    def __init__(self, repository: RiskProfileRepository) -> None:
        self._repository = repository

    def get(self) -> RiskProfileRecord | None:
        return self._repository.get()

    def replace(self, payload: RiskProfileInput) -> RiskProfileRecord:
        values = payload.model_dump()
        values.update(
            {
                "source": RiskProfileSource.CUSTOM,
                "portfolio_fingerprint": None,
                "recommendation_version": None,
            }
        )
        try:
            return self._repository.upsert(values)
        except IntegrityError as exc:
            raise risk_profile_validation("위험 설정 값을 저장할 수 없습니다.") from exc
