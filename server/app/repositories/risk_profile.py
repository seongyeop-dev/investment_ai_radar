from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.models.database import RiskProfileRecord

RISK_PROFILE_ID = "default"


class RiskProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> RiskProfileRecord | None:
        return self._session.get(RiskProfileRecord, RISK_PROFILE_ID)

    def upsert(self, values: Mapping[str, Any]) -> RiskProfileRecord:
        profile = self.get()
        if profile is None:
            profile = RiskProfileRecord(id=RISK_PROFILE_ID, **values)
            self._session.add(profile)
        else:
            for key, value in values.items():
                setattr(profile, key, value)
        self._session.flush()
        self._session.refresh(profile)
        return profile
