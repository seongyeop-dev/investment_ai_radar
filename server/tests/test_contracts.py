from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models.contracts import Recommendation, RecommendationType


def test_recommendation_uses_decimal_and_requires_human_decision() -> None:
    now = datetime.now(UTC)
    recommendation = Recommendation(
        id=uuid4(),
        portfolio_item_id=uuid4(),
        recommendation_type=RecommendationType.INSUFFICIENT_DATA,
        generated_at=now,
        valid_until=now + timedelta(hours=1),
        portfolio_context="계약 검증",
        evidence_ids=[],
        confidence=Decimal("0"),
        trust_score=Decimal("0"),
        data_completeness=Decimal("0"),
    )
    assert recommendation.human_decision_required is True
    assert isinstance(recommendation.confidence, Decimal)
