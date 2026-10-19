from datetime import datetime, timezone
import yfinance as yf
import feedparser
from db import get_conn, query
from urllib.parse import urlencode

STOCKS = {
    "AAPL": ("Apple Inc.", "Technology"),
    "MSFT": ("Microsoft Corporation", "Technology"),
    "NVDA": ("NVIDIA Corporation", "Technology"),
    "GOOGL": ("Alphabet Inc.", "Technology"),
    "AMZN": ("Amazon.com Inc.", "Consumer goods"),
}
NEWS_RSS = "https://news.google.com/rss/search?q={query}+stock+when:7d&hl=en-US&gl=US&ceid=US:en"

def fetch_and_store_prices(tickers=None, period="1mo", interval="1d"):
    tickers = tickers or list(STOCKS)
    inserted = 0
    for ticker in tickers:
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True, threads=False)
        if data is None or data.empty:
            continue
        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)
        rows = []
        for ts, row in data.iterrows():
            close = row.get("Close")
            if close is None:
                continue
            try:
                close = float(close)
                if close <= 0:
                    continue
                def val(key):
                    x = row.get(key)
                    try:
                        return float(x) if x is not None else None
                    except (TypeError, ValueError):
                        return None
                vol = row.get("Volume")
                try:
                    vol = int(vol) if vol is not None else None
                except (TypeError, ValueError):
                    vol = None
                stamp = ts.to_pydatetime()
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                rows.append((ticker, stamp, val("Open"), val("High"), val("Low"), close, vol))
            except (TypeError, ValueError):
                continue
        if rows:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.executemany("""INSERT INTO stock_prices
                    (ticker, price_time, open_price, high_price, low_price, close_price, volume)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(ticker, price_time) DO UPDATE SET
                    open_price=EXCLUDED.open_price, high_price=EXCLUDED.high_price,
                    low_price=EXCLUDED.low_price, close_price=EXCLUDED.close_price,
                    volume=EXCLUDED.volume""", rows)
            inserted += len(rows)
    return inserted

def fetch_news(tickers=None, max_items_per_ticker=10):
    tickers = tickers or list(STOCKS)
    seen = set()
    articles = []

    for ticker in tickers:
        params = {
            "q": f"{ticker} company",
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en"
        }

        rss_url = "https://news.google.com/rss/search?" + urlencode(params)
        feed = feedparser.parse(rss_url)

        for entry in feed.entries[:max_items_per_ticker]:
            url = entry.get("link", "")
            title = entry.get("title", "").strip()

            if not url or not title or url in seen:
                continue

            seen.add(url)
            published = None

            if entry.get("published_parsed"):
                try:
                    import time
                    published = datetime.fromtimestamp(
                        time.mktime(entry.published_parsed),
                        tz=timezone.utc
                    )
                except Exception:
                    published = None

            summary = entry.get("summary", title)
            source = entry.get("source", {}).get(
                "title", "Google News RSS"
            )

            articles.append({
                "title": title,
                "url": url,
                "source": source,
                "published_at": published,
                "tickers": [ticker],
                "content": f"{title}\n\n{summary}"
            })

    return articles


def store_articles(articles):
    inserted = 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            for a in articles:
                cur.execute(
                    """
                    INSERT INTO news_articles
                        (title, url, source, published_at, tickers, content)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                    RETURNING id
                    """,
                    (
                        a["title"],
                        a["url"],
                        a["source"],
                        a["published_at"],
                        a["tickers"],
                        a["content"],
                    ),
                )

                if cur.fetchone():
                    inserted += 1

    return inserted

