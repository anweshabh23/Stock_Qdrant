import os
from dotenv import load_dotenv
from db import get_or_create_demo
from market_data import fetch_and_store_prices, fetch_news, store_articles
from rag import index_unindexed_articles

load_dotenv()

def main():
    user_id = get_or_create_demo()
    tickers = [x.strip().upper() for x in os.getenv("WATCHLIST", "AAPL,MSFT,NVDA,GOOGL,AMZN").split(",") if x.strip()]
    print(f"Refreshing prices for {', '.join(tickers)}...")
    try:
        count = fetch_and_store_prices(tickers)
        print(f"Stored/updated {count} price rows.")
    except Exception as exc:
        print(f"Price ingestion failed: {exc}")
    try:

        articles = fetch_news(tickers)
        print(f"Fetched {len(articles)} articles.", flush=True)
        print("Starting article storage...", flush=True)

        stored = store_articles(articles)
        print(f"Inserted {stored} new articles.", flush=True)
        print(f"Fetched {len(articles)} RSS items; inserted {stored} new articles.")
    except Exception as exc:
        print(f"News ingestion failed: {exc}")
    try:
        indexed = index_unindexed_articles(limit=200)
        print(f"Indexed/upserted {indexed} news vectors in Qdrant.")
    except Exception as exc:
        print(f"Vector indexing failed: {exc}. Check Ollama, Qdrant and embedding model.")
    print(f"Demo user id: {user_id}")

if __name__ == "__main__":
    main()
