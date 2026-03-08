import datetime
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from google import genai
import inngest
import inngest.fast_api

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
        chunks = chunks_and_src.chunks
        source_id = chunks_and_src.source_id or "unknown-source"
        vecs = embed_text(chunks)
        if len(vecs) != len(chunks):
            raise RuntimeError("Embedding output length does not match chunk length.")

        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]

        QdrantStorage().upsert(ids, vecs, payloads)
        return UpsertResult(ingested=len(chunks))

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
inngest.fast_api.serve(app, inngest_client, [ingest_pdf, query_pdf])

@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/readyz")
async def readyz() -> dict[str, str]:
    QdrantStorage()
    return {"status": "ready"}
