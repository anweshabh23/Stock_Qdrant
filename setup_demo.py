from db import get_or_create_demo, execute

def main():
    user_id = get_or_create_demo()
    stocks = [
        ("AAPL", "Apple Inc.", "Technology"),
        ("MSFT", "Microsoft Corporation", "Technology"),
        ("NVDA", "NVIDIA Corporation", "Technology"),
        ("GOOGL", "Alphabet Inc.", "Technology"),
        ("AMZN", "Amazon.com Inc.", "Consumer goods"),
    ]
    for row in stocks:
        execute("""INSERT INTO stocks(ticker, company_name, sector) VALUES (%s,%s,%s)
            ON CONFLICT(ticker) DO UPDATE SET company_name=EXCLUDED.company_name, sector=EXCLUDED.sector""", row)
    print(f"Demo user ready (user id {user_id}). Starting cash is set only when the portfolio is first created.")

if __name__ == "__main__":
    main()
