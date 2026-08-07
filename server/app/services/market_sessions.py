from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_data import MarketSessionCacheRecord, ProviderSyncStateRecord
from app.services.market_calendar import MarketCode, MarketScheduleService


class MarketSessionCacheService:
    def __init__(self, session: Session, schedule: MarketScheduleService) -> None:
        self.session = session
        self.schedule = schedule

    def sync(
        self,
        *,
        start: date,
        days: int,
        dry_run: bool,
        confirm: bool,
    ) -> dict[str, object]:
        if not dry_run and not confirm:
            return {"status": "CONFIRM_REQUIRED", "generated": 0}
        generated = 0
        updated = 0
        now = datetime.now(UTC)
        library_version = version("exchange-calendars")
        for market in MarketCode:
            for offset in range(max(1, min(days, 366))):
                session_date = start + timedelta(days=offset)
                item = self.schedule.adapter.session(market, session_date)
                generated += 1
                if dry_run:
                    continue
                record = self.session.scalar(
                    select(MarketSessionCacheRecord).where(
                        MarketSessionCacheRecord.market == market.value,
                        MarketSessionCacheRecord.session_date == session_date.isoformat(),
                    )
                )
                if record is None:
                    record = MarketSessionCacheRecord(
                        market=market.value,
                        session_date=session_date.isoformat(),
                        market_timezone=item.market_timezone,
                        holiday=item.holiday,
                        early_close=item.early_close,
                        schedule_status=item.schedule_status.value,
                        source=item.source or "exchange_calendars",
                        library_version=library_version,
                        generated_at=now,
                        verified_at=now,
                    )
                    self.session.add(record)
                else:
                    updated += 1
                record.open_at = item.open_at
                record.close_at = item.close_at
                record.holiday = item.holiday
                record.early_close = item.early_close
                record.schedule_status = item.schedule_status.value
                record.source = item.source or "exchange_calendars"
                record.library_version = library_version
                record.generated_at = now
                record.verified_at = now
            if not dry_run:
                provider = f"{market.value}_CALENDAR"
                state = self.session.get(
                    ProviderSyncStateRecord,
                    {"provider": provider, "capability": "MARKET_CALENDAR"},
                )
                if state is None:
                    state = ProviderSyncStateRecord(
                        provider=provider,
                        capability="MARKET_CALENDAR",
                        configured=True,
                        status="READY",
                        consecutive_failures=0,
                        request_count=0,
                        success_count=0,
                    )
                    self.session.add(state)
                state.status = "READY"
                state.last_attempt_at = now
                state.last_success_at = now
                state.last_error_code = None
                state.consecutive_failures = 0
                state.success_count += 1
        if not dry_run:
            self.session.flush()
        return {
            "status": "DRY_RUN" if dry_run else "SUCCEEDED",
            "generated": generated,
            "updated": updated,
            "library": f"exchange-calendars=={library_version}",
        }
