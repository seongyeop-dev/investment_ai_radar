"""Add market briefing preferences and risk wizard fields.

Revision ID: 20260726_0007
Revises: 20260726_0006
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260726_0007"
down_revision: str | None = "20260726_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _percent() -> sa.types.TypeEngine:
    return sa.Numeric(precision=7, scale=4).with_variant(sa.String(length=80), "sqlite")


def _recreate() -> str:
    return "always" if op.get_context().dialect.name == "sqlite" else "auto"


def upgrade() -> None:
    with op.batch_alter_table("briefing_records", recreate=_recreate()) as batch:
        batch.drop_constraint("briefing_type", type_="check")
        batch.create_check_constraint(
            "briefing_type",
            "briefing_type IN ("
            "'CHANGE_BRIEFING', 'KRX_PRE_OPEN', 'KRX_POST_CLOSE', "
            "'NASDAQ_PRE_OPEN', 'NASDAQ_POST_CLOSE', 'DAILY_DIGEST', "
            "'CORRECTION_NOTICE', 'PROVIDER_HEALTH_NOTICE', 'MANUAL_PREVIEW')",
        )

    with op.batch_alter_table("notification_preferences", recreate=_recreate()) as batch:
        for name, default in (
            ("krx_pre_open_enabled", "0"),
            ("krx_post_close_enabled", "0"),
            ("nasdaq_pre_open_enabled", "0"),
            ("nasdaq_post_close_enabled", "0"),
            ("immediate_material_change_enabled", "0"),
            ("include_reentry_watch", "0"),
            ("send_no_material_change_briefing", "0"),
        ):
            batch.add_column(
                sa.Column(
                    name,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(default),
                )
            )
        for name, default in (
            ("krx_pre_open_offset_minutes", "40"),
            ("krx_post_close_offset_minutes", "20"),
            ("nasdaq_pre_open_offset_minutes", "60"),
            ("nasdaq_post_close_offset_minutes", "20"),
        ):
            batch.add_column(
                sa.Column(
                    name,
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text(default),
                )
            )
        for name, column in (
            ("ck_notification_krx_pre_offset", "krx_pre_open_offset_minutes"),
            ("ck_notification_krx_post_offset", "krx_post_close_offset_minutes"),
            (
                "ck_notification_nasdaq_pre_offset",
                "nasdaq_pre_open_offset_minutes",
            ),
            (
                "ck_notification_nasdaq_post_offset",
                "nasdaq_post_close_offset_minutes",
            ),
        ):
            batch.create_check_constraint(name, f"{column} >= 0 AND {column} <= 240")

    with op.batch_alter_table("risk_profiles", recreate=_recreate()) as batch:
        batch.add_column(sa.Column("risk_style", sa.String(length=12)))
        batch.add_column(sa.Column("primary_goal", sa.String(length=20)))
        batch.add_column(sa.Column("default_investment_horizon", sa.String(length=6)))
        batch.add_column(sa.Column("max_single_position_percent", _percent()))
        batch.add_column(sa.Column("portfolio_loss_review_percent", _percent()))
        batch.add_column(sa.Column("default_loss_review_percent", _percent()))
        batch.add_column(sa.Column("default_profit_review_percent", _percent()))
        batch.add_column(sa.Column("minimum_cash_percent", _percent()))
        batch.add_column(sa.Column("max_single_additional_buy_percent", _percent()))
        batch.add_column(sa.Column("averaging_down_policy", sa.String(length=11)))
        batch.add_column(sa.Column("max_averaging_down_count", sa.Integer()))
        batch.add_column(
            sa.Column("require_official_evidence_for_averaging_down", sa.Boolean())
        )
        batch.add_column(sa.Column("high_volatility_asset_limit_percent", _percent()))
        batch.add_column(sa.Column("crypto_asset_limit_percent", _percent()))
        batch.add_column(sa.Column("notes", sa.String(length=4000)))
        batch.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True)))
        batch.create_check_constraint(
            "risk_style",
            "risk_style IS NULL OR risk_style IN "
            "('CONSERVATIVE', 'BALANCED', 'AGGRESSIVE', 'CUSTOM')",
        )
        batch.create_check_constraint(
            "primary_goal",
            "primary_goal IS NULL OR primary_goal IN "
            "('CAPITAL_PRESERVATION', 'INCOME', 'BALANCED_GROWTH', "
            "'GROWTH', 'CUSTOM')",
        )
        batch.create_check_constraint(
            "risk_default_investment_horizon",
            "default_investment_horizon IS NULL OR "
            "default_investment_horizon IN "
            "('SCALP', 'SHORT', 'MEDIUM', 'LONG', 'UNSET')",
        )
        batch.create_check_constraint(
            "averaging_down_policy",
            "averaging_down_policy IS NULL OR averaging_down_policy IN "
            "('DISABLED', 'CONDITIONAL', 'ALLOWED')",
        )
        for name, column, positive in (
            (
                "ck_risk_single_position_review_range",
                "max_single_position_percent",
                True,
            ),
            (
                "ck_risk_portfolio_review_range",
                "portfolio_loss_review_percent",
                True,
            ),
            ("ck_risk_default_loss_review_range", "default_loss_review_percent", True),
            (
                "ck_risk_default_profit_review_range",
                "default_profit_review_percent",
                True,
            ),
            ("ck_risk_minimum_cash_range", "minimum_cash_percent", False),
            (
                "ck_risk_additional_buy_range",
                "max_single_additional_buy_percent",
                False,
            ),
            (
                "ck_risk_high_volatility_range",
                "high_volatility_asset_limit_percent",
                False,
            ),
            ("ck_risk_crypto_limit_range", "crypto_asset_limit_percent", False),
        ):
            lower = ">" if positive else ">="
            batch.create_check_constraint(
                name,
                f"{column} IS NULL OR "
                f"(CAST({column} AS NUMERIC) {lower} 0 "
                f"AND CAST({column} AS NUMERIC) <= 100)",
            )
        batch.create_check_constraint(
            "ck_risk_averaging_count_nonnegative",
            "max_averaging_down_count IS NULL OR max_averaging_down_count >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("risk_profiles", recreate=_recreate()) as batch:
        for name in (
            "ck_risk_averaging_count_nonnegative",
            "ck_risk_crypto_limit_range",
            "ck_risk_high_volatility_range",
            "ck_risk_additional_buy_range",
            "ck_risk_minimum_cash_range",
            "ck_risk_default_profit_review_range",
            "ck_risk_default_loss_review_range",
            "ck_risk_portfolio_review_range",
            "ck_risk_single_position_review_range",
            "averaging_down_policy",
            "risk_default_investment_horizon",
            "primary_goal",
            "risk_style",
        ):
            batch.drop_constraint(name, type_="check")
        for name in (
            "acknowledged_at",
            "notes",
            "crypto_asset_limit_percent",
            "high_volatility_asset_limit_percent",
            "require_official_evidence_for_averaging_down",
            "max_averaging_down_count",
            "averaging_down_policy",
            "max_single_additional_buy_percent",
            "minimum_cash_percent",
            "default_profit_review_percent",
            "default_loss_review_percent",
            "portfolio_loss_review_percent",
            "max_single_position_percent",
            "default_investment_horizon",
            "primary_goal",
            "risk_style",
        ):
            batch.drop_column(name)

    with op.batch_alter_table("notification_preferences", recreate=_recreate()) as batch:
        for name in (
            "ck_notification_nasdaq_post_offset",
            "ck_notification_nasdaq_pre_offset",
            "ck_notification_krx_post_offset",
            "ck_notification_krx_pre_offset",
        ):
            batch.drop_constraint(name, type_="check")
        for name in (
            "nasdaq_post_close_offset_minutes",
            "nasdaq_pre_open_offset_minutes",
            "krx_post_close_offset_minutes",
            "krx_pre_open_offset_minutes",
            "send_no_material_change_briefing",
            "include_reentry_watch",
            "immediate_material_change_enabled",
            "nasdaq_post_close_enabled",
            "nasdaq_pre_open_enabled",
            "krx_post_close_enabled",
            "krx_pre_open_enabled",
        ):
            batch.drop_column(name)

    with op.batch_alter_table("briefing_records", recreate=_recreate()) as batch:
        batch.drop_constraint("briefing_type", type_="check")
        batch.create_check_constraint(
            "briefing_type",
            "briefing_type IN ("
            "'CHANGE_BRIEFING', 'DAILY_DIGEST', 'CORRECTION_NOTICE', "
            "'PROVIDER_HEALTH_NOTICE', 'MANUAL_PREVIEW')",
        )
