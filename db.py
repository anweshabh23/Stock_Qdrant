import os
from contextlib import contextmanager
from decimal import Decimal
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://portfolio_user:portfolio_pass@localhost:5432/portfolio_db")

@contextmanager
def get_conn():
    with psycopg.connect(
    DATABASE_URL,
    row_factory=dict_row,
    connect_timeout=5
    ) as conn:
        yield conn

def query(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

def execute(sql, params=()):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)

def get_or_create_demo():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users(username) VALUES ('demo_user') ON CONFLICT(username) DO UPDATE SET username=EXCLUDED.username RETURNING id")
            user_id = cur.fetchone()["id"]
            cur.execute("""INSERT INTO user_preferences(user_id) VALUES (%s)
                ON CONFLICT(user_id) DO NOTHING""", (user_id,))
            cur.execute("""INSERT INTO portfolios(user_id, cash_balance)
                VALUES (%s, %s) ON CONFLICT(user_id) DO NOTHING""",
                (user_id, Decimal(os.getenv("STARTING_CASH", "100000"))))
            return user_id
