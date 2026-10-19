# RAG-Powered Financial Portfolio Simulator

A local AI-powered financial portfolio simulator that combines Retrieval-Augmented Generation (RAG), vector search, relational database management, and rule-based trading to explore financial news and portfolio performance.

## Overview

This project integrates a local Large Language Model (LLM) with financial news retrieval and structured portfolio data. Users can explore stock prices, review portfolio holdings, ask questions about financial news, and simulate trading decisions through an interactive Streamlit dashboard.

The system uses PostgreSQL as its relational data store, Qdrant for vector-based news retrieval, and Ollama to generate text embeddings and AI responses locally.

**Note:** This is an educational simulation. It does not execute real trades or provide guaranteed investment advice.

## Key Features

- **Portfolio Dashboard:** View portfolio information, holdings, stock prices, and asset allocation.
- **RAG Assistant:** Ask questions about financial news using semantically retrieved articles and relevant portfolio context.
- **Semantic Search:** Retrieve relevant news articles using vector embeddings and Qdrant.
- **Local LLM Integration:** Generate responses using Ollama without relying on a hosted LLM API.
- **Trading Simulator:** Apply rule-based BUY, SELL, and HOLD decisions using price momentum and a simple news sentiment score.
- **Order and Audit Tracking:** Review simulated trading decisions, orders, and transactions.
- **Database Integration:** Store structured financial and portfolio information in PostgreSQL.
- **Containerized Services:** Run PostgreSQL and Qdrant using Docker Compose.

## Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| User interface | Streamlit |
| Relational database | PostgreSQL |
| Vector database | Qdrant |
| Local LLM runtime | Ollama |
| Embedding model | `nomic-embed-text` |
| Chat model | `llama3.2:1b` |
| Containerization | Docker Compose |


PostgreSQL also supports portfolio tracking,
simulated trading, orders, and transaction history.
```

## How RAG Works

1. Financial news articles are collected and processed by the ingestion pipeline.
2. Structured information is stored in PostgreSQL.
3. News text is converted into vector embeddings using Ollama.
4. Embeddings and associated article metadata are stored in Qdrant.
5. When a user asks a question, the question is embedded and similar news articles are retrieved.
6. Retrieved articles and relevant portfolio context are passed to the local LLM.
7. The assistant generates an answer grounded in the available context and presents relevant sources.

## Trading Simulation

The trading module evaluates recent price movement and a simple keyword-based news score to produce BUY, SELL, or HOLD decisions.

The resulting actions are simulated and recorded alongside relevant portfolio changes and transaction history. This is a rule-based educational strategy, not a validated investment model.

## Prerequisites

Install the following before running the project:

- Python 3.10 or a compatible version supported by the dependencies
- Docker Desktop
- Ollama
- Git

## Setup and Installation

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd portfolio_rag_simulator
```

Replace the placeholder with your repository URL.

### 2. Create a virtual environment

On Windows:

```bat
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bat
pip install -r requirements.txt
```

### 4. Start PostgreSQL and Qdrant

Ensure Docker Desktop is running, then execute:

```bat
docker compose up -d
docker compose ps
```

Check `docker-compose.yml` for the configured ports, database name, credentials, and persistent volume settings.

### 5. Configure environment variables

Create a local `.env` file using `.env.example` as a template, if provided. Update the values to match your local configuration.

Do not commit passwords, API keys, or other secrets.

### 6. Start Ollama

Ensure Ollama is running, then download the models used by the project if they are not already installed:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2:1b
```

Check the model names and configuration in your environment file before running the application.

### 7. Initialize the demo data

If the repository includes `setup_demo.py`, run it only when the database has not already been initialized or the demo setup needs to be recreated:

```bash
python setup_demo.py
```

### 8. Ingest financial data

```bash
python ingest.py
```

This fetches available market and news data, updates the database, and indexes news embeddings in Qdrant.

### 9. Launch the dashboard

```bash
streamlit run app.py
```

Open the local URL displayed in the terminal, typically `http://localhost:8501`.

## Project Structure

```text
portfolio_rag_simulator/
├── app.py             # Streamlit dashboard
├── db.py              # Database connection and query helpers
├── trading.py         # Trading simulation logic
├── rag.py             # Embeddings, retrieval, and LLM responses
├── ingest.py          # News and data ingestion pipeline
├── market_data.py     # Market data retrieval
├── setup_demo.py      # Demo database setup
├── init.sql           # Database schema, if included
├── docker-compose.yml # PostgreSQL and Qdrant services
├── requirements.txt   # Python dependencies
├── .gitignore         # Files excluded from Git
└── README.md          # Project documentation
```

The file list above describes the intended project layout. Remove or rename entries in this section to match the actual repository.

## Design Decisions

- **PostgreSQL:** Stores structured portfolio information and transactional records.
- **Qdrant:** Supports semantic retrieval over financial news using vector similarity.
- **Ollama:** Runs embeddings and language generation locally.
- **Streamlit:** Provides an interactive interface for exploring the system.
- **RAG:** Supplies retrieved evidence to the language model instead of relying solely on its internal knowledge.

## Limitations

- Trading decisions use simplified rules and keyword-based news scoring.
- Retrieved news and generated answers may be incomplete or inaccurate.
- Market data availability depends on the external data sources used by the ingestion code.
- Results are intended for experimentation and educational use, not live trading.
- Local model performance depends on available hardware and resources.

## Future Improvements

- Improve financial sentiment analysis beyond keyword matching.
- Add stronger transaction handling and database integrity checks.
- Evaluate retrieval relevance and answer quality.
- Add backtesting, performance metrics, and risk analysis.
- Improve error handling, logging, and automated tests.
- Add monitoring and recovery for failed data ingestion or vector indexing.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
