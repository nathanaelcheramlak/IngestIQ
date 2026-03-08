# RAG Event-Driven API

Production-style Retrieval-Augmented Generation (RAG) service for PDF ingestion and question answering.  
The system is event-driven with durable workflow steps, vector search retrieval, and LLM answer generation.

## Why This Project

This repository demonstrates a practical, deployable RAG architecture that prioritizes:

- Reliable ingestion and query workflows via **Inngest**
- Semantic retrieval at scale via **Qdrant**
- Modern LLM + embeddings via **Google Gemini**
- API-first integration through **FastAPI**

It is intentionally clean and modular so teams can extend it into enterprise use cases (knowledge bases, policy assistants, support copilots, internal search).

## Core Capabilities

- Ingest a PDF into a vector database using an event (`ingest_pdf`)
- Split document text into retrieval-friendly chunks
- Generate 768-dimensional embeddings with `gemini-embedding-001`
- Upsert vectors with deterministic IDs into Qdrant
- Answer user questions through retrieval + generation (`query_pdf`)
- Return sources and context count for traceability

## System Architecture

```text
PDF -> Loader/Chunker -> Embedding Model -> Qdrant (Vector Store)
                                           ^
Question -> Embedding Model -> Similarity Search -> Context Assembly -> Gemini LLM -> Answer
```

### Runtime Components

- **FastAPI**: hosts the Inngest HTTP serving endpoints
- **Inngest Functions**:
  - `Ingest PDF` (event: `ingest_pdf`)
  - `Query PDF` (event: `query_pdf`)
- **QdrantStorage** (`vector_db.py`): vector collection management, upsert, and search
- **Data Loader** (`data_loader.py`): PDF parsing, chunking, and embeddings

## Tech Stack

- Python 3.12+
- FastAPI
- Inngest Python SDK
- Qdrant Cloud / self-hosted Qdrant
- Google GenAI SDK (`google-genai`)
- LlamaIndex file reader + sentence splitter
- Uvicorn
- uv (package/environment manager)

## Repository Layout

```text
.
├── main.py            # FastAPI app + Inngest workflow functions
├── data_loader.py     # PDF loading, chunking, embedding generation
├── vector_db.py       # Qdrant vector storage wrapper
├── custom_types.py    # Pydantic models for typed workflow contracts
├── pyproject.toml     # Dependencies and project metadata
└── README.md
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- `uv` installed
- Qdrant instance (Cloud or self-hosted)
- Google AI Studio / Gemini API key

### 2. Configure Environment

Create `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
QDRANT_ENDPOINT=https://your-qdrant-endpoint:6333
QDRANT_API_KEY=your_qdrant_api_key
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run API Server

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## How To Run

Run the full stack locally in this order:

1. Start the FastAPI app:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Start Inngest dev server (new terminal):

```bash
npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
```

3. Start Streamlit UI (new terminal):

```bash
uv run streamlit run streamlit_app.py
```

## Event Contracts

The service is event-driven. Trigger these events through your Inngest integration.

### `ingest_pdf`

Purpose: parse PDF, chunk text, embed chunks, and upsert into Qdrant.

Payload:

```json
{
  "pdf_path": "/absolute/or/relative/path/to/document.pdf",
  "source_id": "optional-human-friendly-source-name"
}
```

Response:

```json
{
  "ingested": 42
}
```

### `query_pdf`

Purpose: embed question, retrieve nearest chunks, generate answer from retrieved context only.

Payload:

```json
{
  "question": "What does the policy say about incident escalation?",
  "top_k": 5
}
```

Response:

```json
{
  "answer": "Concise grounded answer...",
  "sources": ["policy_v3.pdf"],
  "num_contexts": 5,
  "timestamp": "2026-03-08T12:00:00+00:00"
}
```
