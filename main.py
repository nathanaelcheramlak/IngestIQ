import datetime
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import httpx
import inngest
import inngest.fast_api
from pydantic import BaseModel

from custom_types import ChunkAndSrc, QueryResult, SearchResult, UpsertResult
from data_loader import embed_text, load_and_chunk_pdf
from vector_db import QdrantStorage

load_dotenv()
logger = logging.getLogger("uvicorn")
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is required.")

gemini_client = genai.Client(api_key=gemini_api_key)

inngest_client = inngest.Inngest(
    app_id="rag_app",
    logger=logger,
    is_production=False,
    serializer=inngest.PydanticSerializer(),
)


UPLOADS_DIR = Path("uploads")


def _required_str(data: dict, key: str) -> str:
    value = data.get(key)
    if value is None:
        raise ValueError(f"Missing required field: {key}")
    if not isinstance(value, str):
        raise ValueError(f"Field '{key}' must be a string.")
    value = value.strip()
    if not value:
        raise ValueError(f"Field '{key}' cannot be empty.")
    return value


def _raise_service_unavailable(exc: Exception, operation: str) -> None:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        raise HTTPException(
            status_code=503,
            detail=(
                f"{operation} unavailable: cannot reach external AI service. "
                "Check internet/DNS and retry."
            ),
        ) from exc
    raise HTTPException(status_code=500, detail=f"{operation} failed: {exc}") from exc


def _ingest_pdf_from_path(pdf_path: Path, source_id: str) -> UpsertResult:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    chunks = load_and_chunk_pdf(str(pdf_path))
    if not chunks:
        raise ValueError(f"No readable text content found in: {pdf_path}")

    return _upsert_chunks(chunks, source_id or pdf_path.name)


def _upsert_chunks(chunks: list[str], source_id: str) -> UpsertResult:
    vecs = embed_text(chunks)
    if len(vecs) != len(chunks):
        raise RuntimeError("Embedding output length does not match chunk length.")

    source = source_id or "unknown-source"
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}:{i}")) for i in range(len(chunks))]
    payloads = [{"source": source, "text": chunks[i]} for i in range(len(chunks))]
    QdrantStorage().upsert(ids, vecs, payloads)
    return UpsertResult(ingested=len(chunks))


def _query_answer(question: str, top_k: int) -> QueryResult:
    query_vec = embed_text([question])[0]
    found = QdrantStorage().search(query_vec, top_k)
    contexts = found["contexts"]
    sources = found["sources"]

    context_block = "\n\n".join(f"- {c}" for c in contexts)
    prompt = (
        "Use the following context to answer the question.\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}\n"
        "Answer concisely using only the context above."
    )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"temperature": 0.2, "max_output_tokens": 1024},
    )

    return QueryResult(
        answer=(response.text or "").strip(),
        sources=sources,
        num_contexts=len(contexts),
    )


@inngest_client.create_function(
    fn_id="Ingest PDF",
    trigger=inngest.TriggerEvent(event="ingest_pdf"),
)
async def ingest_pdf(ctx: inngest.Context):
    # Step 1
    def _load(ctx: inngest.Context) -> ChunkAndSrc:
        pdf_path = _required_str(ctx.event.data, "pdf_path")
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        source_id = ctx.event.data.get("source_id", pdf_path)
        if not isinstance(source_id, str):
            source_id = str(source_id)

        chunks = load_and_chunk_pdf(pdf_path)
        if not chunks:
            raise ValueError(f"No readable text content found in: {pdf_path}")
        return ChunkAndSrc(chunks=chunks, source_id=source_id)

    # Step 2
    def _upsert(chunks_and_src: ChunkAndSrc) -> UpsertResult:
        source_id = chunks_and_src.source_id or "unknown-source"
        return _upsert_chunks(chunks_and_src.chunks, source_id)

    chunks_and_src = await ctx.step.run("load-and-chunk", lambda: _load(ctx), output_type=ChunkAndSrc)
    ingested = await ctx.step.run("embed-and-upsert", lambda: _upsert(chunks_and_src), output_type=UpsertResult)

    return ingested.model_dump()  # pydantic to json


@inngest_client.create_function(
    fn_id="Query PDF",
    trigger=inngest.TriggerEvent(event="query_pdf"),
)
async def query_pdf(ctx: inngest.Context):
    def _search(question: str, top_k: int = 5) -> SearchResult:
        query_vec = embed_text([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k)
        return SearchResult(contexts=found["contexts"], sources=found["sources"])

    def _generate_answer(question: str, contexts: list[str], sources: list[str]) -> QueryResult:
        context_block = "\n\n".join(f"- {c}" for c in contexts)
        prompt = (
            "Use the following context to answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {question}\n"
            "Answer concisely using only the context above."
        )

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"temperature": 0.2, "max_output_tokens": 1024},
        )

        answer = (response.text or "").strip()
        return QueryResult(answer=answer, sources=sources, num_contexts=len(contexts))

    question = _required_str(ctx.event.data, "question")
    top_k = int(ctx.event.data.get("top_k", 5))
    top_k = max(1, min(top_k, 20))

    found = await ctx.step.run(
        "embed-and-search",
        lambda: _search(question, top_k),
        output_type=SearchResult,
    )

    llm_output = await ctx.step.run(
        "llm-answer",
        lambda: _generate_answer(question, found.contexts, found.sources),
        output_type=QueryResult,
    )

    return {
        "answer": llm_output.answer,
        "sources": found.sources,
        "num_contexts": len(found.contexts),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
    }


app = FastAPI()

frontend_origins_raw = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
frontend_origins = [o.strip() for o in frontend_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

inngest.fast_api.serve(app, inngest_client, [ingest_pdf, query_pdf])


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


@app.post("/api/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    source_id: str | None = Form(default=None),
) -> dict[str, str | int]:
    filename = Path(file.filename or "document.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    try:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        stored_name = f"{int(datetime.datetime.now(datetime.UTC).timestamp())}-{filename}"
        destination = (UPLOADS_DIR / stored_name).resolve()
        destination.write_bytes(await file.read())

        final_source_id = (source_id or "").strip() or filename
        result = _ingest_pdf_from_path(destination, final_source_id)
        return {
            "source_id": final_source_id,
            "ingested": result.ingested,
            "file_path": str(destination),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to upload/ingest PDF")
        _raise_service_unavailable(exc, "PDF ingestion")


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, str | int | list[str]]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question cannot be empty")

    top_k = max(1, min(int(request.top_k), 20))
    try:
        result = _query_answer(question, top_k)
        return {
            "answer": result.answer,
            "sources": result.sources,
            "num_contexts": result.num_contexts,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    except Exception as exc:
        logger.exception("Chat query failed")
        _raise_service_unavailable(exc, "Chat query")

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/readyz")
async def readyz() -> dict[str, str]:
    QdrantStorage()
    return {"status": "ready"}
