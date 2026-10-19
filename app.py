
import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

from db import query, execute, get_or_create_demo
from rag import retrieve_news, ask_local_llm
from trading import run_strategy

load_dotenv()

st.set_page_config(
    page_title="Personalized AI Portfolio",
    page_icon="📈",
    layout="wide",
)

st.title("AI-Powered Portfolio Simulator")
st.caption(
    "Academic prototype · simulated trades only · "
    "market data may be delayed or unavailable"
)

# Database connection and portfolio
try:
    user_id = get_or_create_demo()
    portfolio_rows = query(
        "SELECT * FROM portfolios WHERE user_id=%s",
        (user_id,),
    )

    if not portfolio_rows:
        st.error(
            "No portfolio exists for the demo user. "
            "Run `python setup_demo.py`."
        )
        st.stop()

    portfolio = portfolio_rows[0]

except Exception as exc:
    st.error(
        "Cannot connect to PostgreSQL. Start Docker Compose "
        "and run `python setup_demo.py`."
    )
    st.exception(exc)
    st.stop()

portfolio_id = portfolio["id"]

# Load portfolio holdings
holdings = query(
    """
    SELECT
        h.ticker,
        h.quantity,
        h.average_cost,
        COALESCE(p.close_price, 0) AS latest_price
    FROM holdings h
    LEFT JOIN (
        SELECT DISTINCT ON (ticker) ticker, close_price
        FROM stock_prices
        ORDER BY ticker, price_time DESC
    ) p USING (ticker)
    WHERE h.portfolio_id=%s
    ORDER BY h.ticker
    """,
    (portfolio_id,),
)

cash = float(portfolio["cash_balance"])
holding_value = sum(
    float(row["quantity"]) * float(row["latest_price"])
    for row in holdings
)
invested_cost = sum(
    float(row["quantity"]) * float(row["average_cost"])
    for row in holdings
)
portfolio_value = cash + holding_value
unrealized_pl = holding_value - invested_cost

tabs = st.tabs(
    [
        "Overview",
        "Profile",
        "RAG Assistant",
        "Trading Simulator",
        "Orders & Audit",
        "System",
    ]
)

# ---------------------------------------------------------
# 1. OVERVIEW
# ---------------------------------------------------------
with tabs[0]:
    st.subheader("Portfolio overview")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portfolio value", f"₹{portfolio_value:,.2f}")
    c2.metric("Cash balance", f"₹{cash:,.2f}")
    c3.metric("Holdings value", f"₹{holding_value:,.2f}")
    c4.metric("Unrealized P/L", f"₹{unrealized_pl:,.2f}")

    prices = query(
        """
        SELECT DISTINCT ON (sp.ticker)
            sp.ticker,
            s.company_name,
            sp.close_price,
            sp.price_time
        FROM stock_prices sp
        JOIN stocks s USING (ticker)
        ORDER BY sp.ticker, sp.price_time DESC
        """
    )

    st.subheader("Latest available prices")

    if prices:
        price_df = pd.DataFrame(prices)
        price_df["close_price"] = pd.to_numeric(
            price_df["close_price"]
        )

        price_df = price_df.rename(
            columns={
                "ticker": "Ticker",
                "company_name": "Company",
                "close_price": "Latest close",
                "price_time": "Timestamp",
            }
        )

        st.dataframe(
            price_df,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info(
            "No prices are available yet. Run `python ingest.py`."
        )

    st.subheader("Holdings")

    if holdings:
        holdings_df = pd.DataFrame(holdings)

        for column in [
            "quantity",
            "average_cost",
            "latest_price",
        ]:
            holdings_df[column] = pd.to_numeric(
                holdings_df[column]
            )

        holdings_df["market_value"] = (
            holdings_df["quantity"]
            * holdings_df["latest_price"]
        )

        holdings_df["unrealized_p_l"] = (
            holdings_df["market_value"]
            - holdings_df["quantity"]
            * holdings_df["average_cost"]
        )

        st.dataframe(
            holdings_df,
            width="stretch",
            hide_index=True,
        )

        chart_df = holdings_df[
            holdings_df["market_value"] > 0
        ]

        if not chart_df.empty:
            st.plotly_chart(
                px.pie(
                    chart_df,
                    values="market_value",
                    names="ticker",
                    title="Holdings allocation",
                ),
                width="stretch",
            )
    else:
        st.info(
            "No holdings yet. Run the simulated strategy "
            "after market data is available."
        )

# ---------------------------------------------------------
# 2. PROFILE
# ---------------------------------------------------------
with tabs[1]:
    st.subheader("Investor profile")

    prefs_rows = query(
        "SELECT * FROM user_preferences WHERE user_id=%s",
        (user_id,),
    )

    if not prefs_rows:
        st.error(
            "No preferences record was found for the demo user."
        )
    else:
        prefs = prefs_rows[0]

        p1, p2, p3 = st.columns(3)

        p1.metric(
            "Risk profile",
            str(prefs["risk_profile"]),
        )

        p2.metric(
            "Investment horizon",
            str(prefs["investment_horizon"]),
        )

        p3.metric(
            "Automated simulated execution",
            (
                "Enabled"
                if prefs["automation_enabled"]
                else "Disabled"
            ),
        )

        st.write("**Preferred sectors**")

        sectors_current = prefs["preferred_sectors"] or []

        st.write(
            ", ".join(sectors_current)
            if sectors_current
            else "No preferred sectors selected."
        )

        st.divider()
        st.subheader("Edit preferences")

        risk_options = [
            "Conservative",
            "Moderate",
            "Aggressive",
        ]

        horizon_options = [
            "Short-term",
            "Medium-term",
            "Long-term",
        ]

        with st.form("profile_preferences_form"):
            risk = st.selectbox(
                "Risk profile",
                risk_options,
                index=(
                    risk_options.index(prefs["risk_profile"])
                    if prefs["risk_profile"] in risk_options
                    else 1
                ),
            )

            horizon = st.selectbox(
                "Investment horizon",
                horizon_options,
                index=(
                    horizon_options.index(
                        prefs["investment_horizon"]
                    )
                    if prefs["investment_horizon"] in horizon_options
                    else 2
                ),
            )

            sectors = st.multiselect(
                "Preferred sectors",
                [
                    "Technology",
                    "Healthcare",
                    "Banking",
                    "Energy",
                    "Consumer goods",
                ],
                default=sectors_current,
            )

            automation = st.checkbox(
                "Enable automated simulated execution",
                value=bool(prefs["automation_enabled"]),
            )

            save_preferences = st.form_submit_button(
                "Save preferences",
            )

        if save_preferences:
            execute(
                """
                UPDATE user_preferences
                SET risk_profile=%s,
                    investment_horizon=%s,
                    preferred_sectors=%s,
                    automation_enabled=%s,
                    updated_at=NOW()
                WHERE user_id=%s
                """,
                (
                    risk,
                    horizon,
                    sectors,
                    automation,
                    user_id,
                ),
            )

            st.success("Preferences saved.")
            st.rerun()

    st.divider()
    st.subheader("Portfolio summary")

    s1, s2, s3 = st.columns(3)

    s1.metric(
        "Portfolio value",
        f"₹{portfolio_value:,.2f}",
    )

    s2.metric(
        "Available cash",
        f"₹{cash:,.2f}",
    )

    s3.metric(
        "Unrealized P/L",
        f"₹{unrealized_pl:,.2f}",
    )

    if holdings:
        profile_holdings_df = pd.DataFrame(holdings)

        profile_holdings_df["market_value"] = (
            pd.to_numeric(profile_holdings_df["quantity"])
            * pd.to_numeric(
                profile_holdings_df["latest_price"]
            )
        )

        st.dataframe(
            profile_holdings_df[
                [
                    "ticker",
                    "quantity",
                    "average_cost",
                    "latest_price",
                    "market_value",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Your portfolio currently has no holdings.")

    st.caption(
        "Preferences are stored in PostgreSQL. The current "
        "strategy is an educational heuristic and does not yet "
        "automatically adapt its rules to your profile."
    )

# ---------------------------------------------------------
# 3. RAG ASSISTANT
# ---------------------------------------------------------
with tabs[2]:
    st.subheader("Ask questions grounded in retrieved news")

    st.write(
        "The assistant searches locally indexed news and uses "
        "the local Ollama model to generate an answer."
    )

    ticker_filter = st.selectbox(
        "Optional ticker filter",
        [
            "All tickers",
            "AAPL",
            "MSFT",
            "NVDA",
            "GOOGL",
            "AMZN",
        ],
        key="rag_ticker_filter",
    )

    question = st.text_area(
        "Question",
        placeholder=(
            "Summarize recent news about NVDA and explain "
            "what evidence was retrieved."
        ),
        key="rag_question",
    )

    if st.button(
        "Retrieve evidence and answer",
        type="primary",
        key="rag_retrieve_answer",
    ):
        if not question.strip():
            st.warning("Enter a question first.")
        else:
            try:
                with st.status(
                    "Processing your question...",
                    expanded=True,
                ) as status:

                    st.write(
                        "Step 1/3: Embedding your question "
                        "and searching news..."
                    )

                    hits = retrieve_news(
                        question,
                        limit=5,
                        ticker=(
                            None
                            if ticker_filter == "All tickers"
                            else ticker_filter
                        ),
                    )

                    st.write(
                        f"Step 2/3: Retrieved {len(hits)} "
                        "news articles."
                    )

                    current_holdings = query(
                        """
                        SELECT ticker, quantity, average_cost
                        FROM holdings
                        WHERE portfolio_id=%s
                        ORDER BY ticker
                        """,
                        (portfolio_id,),
                    )

                    holdings_context = (
                        f"Cash balance: {portfolio['cash_balance']}. "
                        f"Holdings: {current_holdings}"
                    )

                    context = "\n\n".join(
                        (
                            f"Title: {hit['title']}\n"
                            f"Source: {hit['source']}\n"
                            f"Date: {hit['published_at']}\n"
                            f"URL: {hit['url']}\n"
                            f"Text: {hit['text']}\n"
                            f"Similarity: {hit['score']:.3f}"
                        )
                        for hit in hits
                    )

                    st.write(
                        "Step 3/3: Generating an answer "
                        "with the local model..."
                    )

                    answer = ask_local_llm(
                        question,
                        context,
                        holdings_context,
                    )

                    status.update(
                        label="Answer generated.",
                        state="complete",
                        expanded=False,
                    )

                st.subheader("Answer")
                st.markdown(answer)

                st.subheader("Retrieved sources")

                if hits:
                    for hit in hits:
                        title = (
                            hit["title"] or "Untitled article"
                        )
                        url = hit["url"]

                        source_line = (
                            f" · {hit['source']}"
                            if hit.get("source")
                            else ""
                        )

                        date_line = (
                            f" · {hit['published_at']}"
                            if hit.get("published_at")
                            else ""
                        )

                        similarity = f"{hit['score']:.3f}"

                        if url:
                            st.markdown(
                                f"- [{title}]({url})"
                                f"{source_line}{date_line} "
                                f"· Similarity: {similarity}"
                            )
                        else:
                            st.write(
                                f"- {title}"
                                f"{source_line}{date_line} "
                                f"· Similarity: {similarity}"
                            )
                else:
                    st.info(
                        "No relevant news was retrieved. "
                        "Try another question or run "
                        "`python ingest.py` to refresh the corpus."
                    )

            except Exception as exc:
                st.error(
                    "The RAG request failed. Check Qdrant and Ollama."
                )
                st.exception(exc)

# ---------------------------------------------------------
# 4. TRADING SIMULATOR
# ---------------------------------------------------------
with tabs[3]:
    st.subheader("Run the educational trading rule")

    st.warning(
        "All orders are simulated. This starter strategy is "
        "an educational heuristic, not a validated or "
        "profitable trading strategy."
    )

    st.write(
        "The strategy checks recent price momentum and a "
        "simple news keyword score. It may return HOLD when "
        "its configured conditions are not met."
    )

    max_position_pct = float(
        os.getenv("MAX_POSITION_PCT", "0.20")
    )

    buy_momentum_pct = float(
        os.getenv("BUY_MOMENTUM_PCT", "1.0")
    )

    sell_momentum_pct = float(
        os.getenv("SELL_MOMENTUM_PCT", "-1.5")
    )

    st.caption(
        f"Current configuration: maximum position "
        f"{max_position_pct:.0%} · "
        f"buy momentum threshold {buy_momentum_pct:.2f}% · "
        f"sell momentum threshold {sell_momentum_pct:.2f}%."
    )

    if st.button(
        "Run strategy once",
        type="primary",
        key="trading_run_strategy",
    ):
        try:
            with st.spinner(
                "Evaluating prices, news scores, and simulated orders..."
            ):
                outcomes = run_strategy(
                    user_id,
                    max_position_pct=max_position_pct,
                    buy_momentum_pct=buy_momentum_pct,
                    sell_momentum_pct=sell_momentum_pct,
                )

            st.subheader("Strategy results")

            for outcome in outcomes:
                st.write(f"• {outcome}")

            st.info(
                "Review the Orders & Audit tab to inspect "
                "recorded orders and decisions."
            )

        except Exception as exc:
            st.error("Strategy execution failed.")
            st.exception(exc)

    st.caption(
        "Execution is user-triggered. Automated scheduling, "
        "profile-specific limits, and backtesting are not "
        "implemented in this version."
    )

# ---------------------------------------------------------
# 5. ORDERS & AUDIT
# ---------------------------------------------------------
with tabs[4]:
    st.subheader("Simulated orders")

    orders = query(
        """
        SELECT
            id,
            ticker,
            side,
            quantity,
            requested_price,
            status,
            reason,
            created_at
        FROM orders
        WHERE portfolio_id=%s
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (portfolio_id,),
    )

    if orders:
        st.dataframe(
            pd.DataFrame(orders),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No simulated orders recorded yet.")

    st.subheader("Strategy decision audit")

    decisions = query(
        """
        SELECT
            ticker,
            action,
            price,
            momentum_pct,
            news_score,
            explanation,
            created_at
        FROM trade_decisions
        WHERE portfolio_id=%s
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (portfolio_id,),
    )

    if decisions:
        st.dataframe(
            pd.DataFrame(decisions),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No strategy decisions recorded yet.")

    st.subheader("Executed simulated transactions")

    transactions = query(
        """
        SELECT
            ticker,
            side,
            quantity,
            execution_price,
            total_value,
            executed_at
        FROM transactions
        WHERE portfolio_id=%s
        ORDER BY executed_at DESC
        LIMIT 100
        """,
        (portfolio_id,),
    )

    if transactions:
        st.dataframe(
            pd.DataFrame(transactions),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No simulated transactions recorded yet.")

# ---------------------------------------------------------
# 6. SYSTEM
# ---------------------------------------------------------
with tabs[5]:
    st.subheader("Service checks")
    st.write("PostgreSQL: connected")

    qdrant_url = os.getenv(
        "QDRANT_URL",
        "http://localhost:6333",
    ).rstrip("/")

    ollama_url = os.getenv(
        "OLLAMA_URL",
        "http://localhost:11434",
    ).rstrip("/")

    try:
        qdrant_response = requests.get(
            f"{qdrant_url}/healthz",
            timeout=3,
        )

        st.write(
            "Qdrant:",
            (
                "reachable"
                if qdrant_response.ok
                else f"HTTP {qdrant_response.status_code}"
            ),
        )

    except Exception as exc:
        st.write("Qdrant: unavailable")
        st.caption(str(exc))

    try:
        ollama_response = requests.get(
            f"{ollama_url}/api/tags",
            timeout=3,
        )

        st.write(
            "Ollama:",
            (
                "reachable"
                if ollama_response.ok
                else f"HTTP {ollama_response.status_code}"
            ),
        )

        if ollama_response.ok:
            model_names = [
                model.get("name", "unknown")
                for model in (
                    ollama_response.json().get("models", [])
                )
            ]

            st.write("Installed local models:", model_names)

    except Exception as exc:
        st.write("Ollama: unavailable")
        st.caption(str(exc))

    st.markdown("#### DBMS queries to demonstrate")

    st.code(
        """-- Latest price for each ticker
SELECT DISTINCT ON (ticker) ticker, close_price, price_time
FROM stock_prices
ORDER BY ticker, price_time DESC;

-- Recent simulated transactions
SELECT ticker, side, quantity, execution_price, total_value, executed_at
FROM transactions
WHERE portfolio_id = <your_portfolio_id>
ORDER BY executed_at DESC;

-- Inspect price-history index
EXPLAIN ANALYZE
SELECT close_price
FROM stock_prices
WHERE ticker = 'NVDA'
ORDER BY price_time DESC
LIMIT 20;""",
        language="sql",
    )
