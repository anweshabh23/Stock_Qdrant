import os
import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from db import query
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "financial_news")

def embed(text):
    response = requests.post(f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": text}, timeout=120)
    response.raise_for_status()
    data = response.json()
    vectors = data.get("embeddings")
    if not vectors:
        raise RuntimeError("Ollama returned no embeddings. Check that the embedding model is installed.")
    return vectors[0]

def qdrant_client():
    return QdrantClient(url=QDRANT_URL, timeout=30)

def ensure_collection(vector_size):
    client = qdrant_client()
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE)
        )
    return client

def index_unindexed_articles(limit=100):
    articles = query(
        "SELECT id,title,url,source,published_at,tickers,content FROM news_articles ORDER BY ingested_at DESC LIMIT %s",
        (limit,)
    )
    if not articles:
        return 0
    # Re-upsert is safe; stable Qdrant point IDs prevent duplicate points.
    vectors = []
    for article in articles:
        text = f"Title: {article['title']}\nSource: {article['source']}\nContent: {article['content']}"
        vectors.append((article, embed(text), text))
    size = len(vectors[0][1])
    client = ensure_collection(size)
    points = []
    for article, vector, text in vectors:
        points.append(models.PointStruct(
            id=int(article["id"]),
            vector=vector,
            payload={
                "article_id": int(article["id"]), "title": article["title"],
                "url": article["url"], "source": article["source"],
                "published_at": article["published_at"].isoformat() if article["published_at"] else None,
                "tickers": article["tickers"] or [], "text": text
            }))
    client.upsert(collection_name=COLLECTION, points=points, wait=True)
    return len(points)

def retrieve_news(question, limit=5, ticker=None):
    vector = embed(question)
    client = qdrant_client()
    if not client.collection_exists(COLLECTION):
        return []
    query_filter = None
    if ticker:
        query_filter = models.Filter(must=[
            models.FieldCondition(key="tickers", match=models.MatchValue(value=ticker))
        ])
    result = client.query_points(collection_name=COLLECTION, query=vector,
        query_filter=query_filter, limit=limit, with_payload=True)
    hits = []
    for point in result.points:
        payload = point.payload or {}
        hits.append({
            "score": point.score, "title": payload.get("title", ""),
            "url": payload.get("url", ""), "source": payload.get("source", ""),
            "published_at": payload.get("published_at", ""),
            "text": payload.get("text", "")
        })
    return hits


def ask_local_llm(question, context, portfolio_context=""):
    prompt = f"""You are a cautious financial-information assistant for an academic simulated portfolio application.
Use only the supplied retrieved news and portfolio facts for claims about current events or the user's portfolio.
If evidence is missing or uncertain, say so. Do not claim news caused a price move unless evidence establishes it.
Do not promise returns or provide personalized real-money investment advice.
Every trade is simulated. Do not execute trades or invent prices.
Answer clearly and include source titles/URLs when available.

PORTFOLIO FACTS:
{portfolio_context or 'No portfolio facts supplied.'}

RETRIEVED NEWS:
{context or 'No relevant news was retrieved.'}

USER QUESTION:
{question}
"""

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_predict": 300
            }
        },
        timeout=(5, 180)
    )
    response.raise_for_status()

    data = response.json()
    answer = data.get("message", {}).get("content", "").strip()

    if not answer:
        raise RuntimeError("Ollama returned an empty answer.")

    return answer


