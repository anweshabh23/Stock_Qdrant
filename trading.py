from decimal import Decimal, ROUND_DOWN
from db import get_conn, query

def latest_prices():
    return query("""SELECT DISTINCT ON (ticker) ticker, close_price, price_time
        FROM stock_prices ORDER BY ticker, price_time DESC""")

def news_keyword_score(ticker):
    rows = query("""SELECT title, content FROM news_articles
        WHERE %s = ANY(tickers) ORDER BY published_at DESC NULLS LAST LIMIT 10""", (ticker,))
    positive = ["beats estimates", "record revenue", "growth", "upgrade", "surge", "profit rises", "strong demand", "partnership"]
    negative = ["misses estimates", "downgrade", "lawsuit", "investigation", "decline", "falls", "weak demand", "cuts forecast"]
    score = 0
    for row in rows:
        text = f"{row['title']} {row['content']}".lower()
        score += sum(1 for term in positive if term in text)
        score -= sum(1 for term in negative if term in text)
    return max(-5, min(5, score))

def decide_action(momentum_pct, news_score, held_qty):
    # Educational heuristic only, not an investment strategy.
    if momentum_pct >= 1.0 and news_score > 0:
        return "BUY", "Positive recent momentum and a positive keyword score met the demo rule."
    if momentum_pct <= -1.5 or news_score < 0:
        if held_qty > 0:
            return "SELL", "Negative momentum or a negative keyword score met the demo rule."
    return "HOLD", "The demo buy/sell conditions were not met."

def run_strategy(user_id, max_position_pct=0.20, buy_momentum_pct=1.0, sell_momentum_pct=-1.5):
    prefs = query("SELECT * FROM user_preferences WHERE user_id=%s", (user_id,))
    portfolio_rows = query("SELECT * FROM portfolios WHERE user_id=%s", (user_id,))
    if not portfolio_rows:
        return ["No portfolio found."]
    portfolio = portfolio_rows[0]
    portfolio_id = portfolio["id"]
    pref = prefs[0] if prefs else {}
    price_rows = query("""SELECT ticker, close_price, price_time FROM (
        SELECT DISTINCT ON (ticker) ticker, close_price, price_time
        FROM stock_prices ORDER BY ticker, price_time DESC) p""")
    outcomes = []
    for current in price_rows:
        ticker = current["ticker"]
        history = query("""SELECT close_price FROM stock_prices WHERE ticker=%s
            ORDER BY price_time DESC LIMIT 2""", (ticker,))
        if len(history) < 2:
            continue
        latest = Decimal(str(history[0]["close_price"]))
        previous = Decimal(str(history[1]["close_price"]))
        if previous == 0:
            continue
        momentum = float((latest - previous) / previous * Decimal("100"))
        score = news_keyword_score(ticker)
        held = query("SELECT quantity, average_cost FROM holdings WHERE portfolio_id=%s AND ticker=%s",
                     (portfolio_id, ticker))
        qty = Decimal(str(held[0]["quantity"])) if held else Decimal("0")
        action, reason = decide_action(momentum, score, qty)
        if action == "BUY" and momentum < buy_momentum_pct:
            action, reason = "HOLD", "Momentum is below the configured buy threshold."
        if action == "SELL" and momentum > sell_momentum_pct and score >= 0:
            action, reason = "HOLD", "Sell threshold not met after validation."
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO trade_decisions
                    (portfolio_id,ticker,action,price,momentum_pct,news_score,explanation)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (portfolio_id,ticker,action,latest,momentum,score,reason))
                if action == "HOLD":
                    outcomes.append(f"{ticker}: HOLD — {reason}")
                    continue
                cur.execute("SELECT cash_balance FROM portfolios WHERE id=%s FOR UPDATE", (portfolio_id,))
                cash = Decimal(str(cur.fetchone()["cash_balance"]))
                if action == "BUY":
                    current_value = qty * latest
                    equity_est = cash + current_value
                    max_value = equity_est * Decimal(str(max_position_pct))
                    allowed_value = max_value - current_value
                    spend = min(cash, max(Decimal("0"), allowed_value))
                    buy_qty = (spend / latest).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
                    if buy_qty <= 0:
                        action = "HOLD"
                        reason = "Insufficient cash or position limit reached."
                        cur.execute(
                        """
                        UPDATE trade_decisions
                        SET action=%s, explanation=%s
                        WHERE portfolio_id=%s AND ticker=%s
                        AND created_at = (
                        SELECT MAX(created_at)
                        FROM trade_decisions
                        WHERE portfolio_id=%s AND ticker=%s
                        )
                        """,
                        ("HOLD", reason, portfolio_id, ticker, portfolio_id, ticker),
                        )
                        outcomes.append(f"{ticker}: HOLD — {reason}")
                    else:
                        total = (buy_qty * latest).quantize(Decimal("0.01"))
                        cur.execute("""INSERT INTO orders(portfolio_id,ticker,side,quantity,requested_price,status,reason)
                            VALUES (%s,%s,'BUY',%s,%s,'FILLED',%s) RETURNING id""",
                            (portfolio_id,ticker,buy_qty,latest,reason))
                        order_id = cur.fetchone()["id"]
                        cur.execute("UPDATE portfolios SET cash_balance=cash_balance-%s WHERE id=%s", (total,portfolio_id))
                        old_qty = qty
                        old_cost = Decimal(str(held[0]["average_cost"])) if held else Decimal("0")
                        new_qty = old_qty + buy_qty
                        avg = ((old_qty * old_cost + buy_qty * latest) / new_qty).quantize(Decimal("0.0001"))
                        cur.execute("""INSERT INTO holdings(portfolio_id,ticker,quantity,average_cost)
                            VALUES (%s,%s,%s,%s)
                            ON CONFLICT(portfolio_id,ticker) DO UPDATE SET quantity=EXCLUDED.quantity,
                            average_cost=EXCLUDED.average_cost,updated_at=NOW()""",
                            (portfolio_id,ticker,new_qty,avg))
                        cur.execute("""INSERT INTO transactions(order_id,portfolio_id,ticker,side,quantity,execution_price,total_value)
                            VALUES (%s,%s,%s,'BUY',%s,%s,%s)""",
                            (order_id,portfolio_id,ticker,buy_qty,latest,total))
                        outcomes.append(f"{ticker}: SIMULATED BUY {buy_qty} at {latest}")
                elif action == "SELL":
                    sell_qty = qty.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
                    if sell_qty <= 0:
                        action, reason = "HOLD", "No shares are available to sell."
                    else:
                        total = (sell_qty * latest).quantize(Decimal("0.01"))
                        cur.execute("""INSERT INTO orders(portfolio_id,ticker,side,quantity,requested_price,status,reason)
                            VALUES (%s,%s,'SELL',%s,%s,'FILLED',%s) RETURNING id""",
                            (portfolio_id,ticker,sell_qty,latest,reason))
                        order_id = cur.fetchone()["id"]
                        cur.execute("UPDATE portfolios SET cash_balance=cash_balance+%s WHERE id=%s", (total,portfolio_id))
                        cur.execute("""UPDATE holdings SET quantity=0,average_cost=0,updated_at=NOW()
                            WHERE portfolio_id=%s AND ticker=%s""", (portfolio_id,ticker))
                        cur.execute("""INSERT INTO transactions(order_id,portfolio_id,ticker,side,quantity,execution_price,total_value)
                            VALUES (%s,%s,%s,'SELL',%s,%s,%s)""",
                            (order_id,portfolio_id,ticker,sell_qty,latest,total))
                        outcomes.append(f"{ticker}: SIMULATED SELL {sell_qty} at {latest}")
    return outcomes or ["No eligible stock history yet. Run data ingestion first."]
