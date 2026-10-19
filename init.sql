CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    risk_profile TEXT NOT NULL DEFAULT 'Moderate'
        CHECK (risk_profile IN ('Conservative', 'Moderate', 'Aggressive')),
    investment_horizon TEXT NOT NULL DEFAULT 'Long-term'
        CHECK (investment_horizon IN ('Short-term', 'Medium-term', 'Long-term')),
    preferred_sectors TEXT[] NOT NULL DEFAULT ARRAY['Technology']::TEXT[],
    automation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolios (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    cash_balance NUMERIC(18,2) NOT NULL CHECK (cash_balance >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector TEXT NOT NULL DEFAULT 'Unknown'
);

CREATE TABLE IF NOT EXISTS stock_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    price_time TIMESTAMPTZ NOT NULL,
    open_price NUMERIC(18,4),
    high_price NUMERIC(18,4),
    low_price NUMERIC(18,4),
    close_price NUMERIC(18,4) NOT NULL CHECK (close_price > 0),
    volume BIGINT,
    source TEXT NOT NULL DEFAULT 'yfinance',
    UNIQUE (ticker, price_time)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_time ON stock_prices(ticker, price_time DESC);

CREATE TABLE IF NOT EXISTS holdings (
    portfolio_id BIGINT NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    quantity NUMERIC(18,6) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    average_cost NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (average_cost >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (portfolio_id, ticker)
);

CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    tickers TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    content TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id BIGINT NOT NULL REFERENCES portfolios(id),
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC(18,6) NOT NULL CHECK (quantity > 0),
    requested_price NUMERIC(18,4) NOT NULL CHECK (requested_price > 0),
    status TEXT NOT NULL CHECK (status IN ('FILLED', 'REJECTED')),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL UNIQUE REFERENCES orders(id),
    portfolio_id BIGINT NOT NULL REFERENCES portfolios(id),
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC(18,6) NOT NULL CHECK (quantity > 0),
    execution_price NUMERIC(18,4) NOT NULL CHECK (execution_price > 0),
    total_value NUMERIC(18,2) NOT NULL CHECK (total_value > 0),
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trade_decisions (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id BIGINT NOT NULL REFERENCES portfolios(id),
    ticker TEXT NOT NULL REFERENCES stocks(ticker),
    action TEXT NOT NULL CHECK (action IN ('BUY', 'SELL', 'HOLD')),
    price NUMERIC(18,4),
    momentum_pct NUMERIC(10,4),
    news_score INTEGER NOT NULL DEFAULT 0,
    explanation TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decisions_portfolio_time ON trade_decisions(portfolio_id, created_at DESC);
