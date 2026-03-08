import os
from google import genai
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is required.")

client = genai.Client(api_key=gemini_api_key)
EMBEDDING_MODEL = "gemini-embedding-001"

splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200) # Characters

def load_and_chunk_pdf(path: str) -> list[str]:
    docs = PDFReader().load_data(file=path)
    texts = [doc.text for doc in docs if getattr(doc, "text", "None")]
    chunks = []
    for text in texts:
        chunks.extend(splitter.split_text(text))

    return chunks

def embed_text(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config={
            "output_dimensionality": 768
        }
    )

    return [embedding.values for embedding in response.embeddings]
