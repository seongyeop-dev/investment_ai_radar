"""HTTP API routers."""

from app.api.analysis import router as analysis_router
from app.api.analyst_references import router as analyst_references_router
from app.api.briefings import router as briefings_router
from app.api.disclosures import router as disclosures_router
from app.api.instruments import router as instruments_router
from app.api.market_briefings import router as market_briefings_router
from app.api.news import router as news_router
from app.api.operations import router as operations_router
from app.api.portfolio import router as portfolio_router
from app.api.providers import router as providers_router
from app.api.risk_profile import router as risk_profile_router

__all__ = [
    "analyst_references_router",
    "analysis_router",
    "briefings_router",
    "disclosures_router",
    "instruments_router",
    "market_briefings_router",
    "news_router",
    "operations_router",
    "portfolio_router",
    "providers_router",
    "risk_profile_router",
]
