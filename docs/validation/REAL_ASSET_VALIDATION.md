# Real Asset Portfolio Validation

This environment validates the application with publicly identifiable assets
without importing a brokerage account or personal investment database.

## Validation assets

- Samsung Electronics (`005930`, KRX, equity)
- Microsoft (`MSFT`, NASDAQ, equity)
- Bitcoin (`BTC`, UPBIT, crypto)

These records are entered manually through the Web interface for functional
validation. Quantity, average purchase price, account credentials, API keys,
and private portfolio data are not required.

## Runtime storage

The validation database is stored only at:

`.local/portfolio_validation/portfolio_validation.db`

The `.local` directory and SQLite database remain excluded from Git.

## Start and stop

Start:

`scripts/start_portfolio_validation.ps1`

Stop:

`scripts/stop_portfolio_validation.ps1`

The startup flow applies Alembic migrations but does not insert fictional
companies, fictional disclosures, fictional news, or seeded portfolio items.