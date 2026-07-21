from pathlib import Path
import os
import time
from uuid import uuid4

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec


KNOWLEDGE_DIR = Path("data/knowledge")
INDEX_NAME_ENV = "PINECONE_INDEX_NAME"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
NAMESPACE = "coverage_rules"


def read_markdown_documents() -> list[dict]:
    documents = []

    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()

        if not text:
            continue

        documents.append(
            {
                "source": str(path),
                "title": path.stem,
                "text": text,
            }
        )

    if not documents:
        raise ValueError(f"No markdown documents found in {KNOWLEDGE_DIR}")

    return documents


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def get_pinecone_client() -> Pinecone:
    api_key = os.getenv("PINECONE_API_KEY")

    if not api_key:
        raise ValueError("Missing PINECONE_API_KEY in .env")

    return Pinecone(api_key=api_key)


def ensure_index(pc: Pinecone, index_name: str) -> None:
    existing_indexes = [idx["name"] for idx in pc.list_indexes()]

    if index_name in existing_indexes:
        print(f"Pinecone index already exists: {index_name}")
        return

    print(f"Creating Pinecone index: {index_name}")

    pc.create_index(
        name=index_name,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1",
        ),
    )

    while not pc.describe_index(index_name).status["ready"]:
        print("Waiting for Pinecone index to be ready...")
        time.sleep(2)

    print("Pinecone index ready.")


def main():
    print("Starting Pinecone ingestion...")

    load_dotenv()

    index_name = os.getenv(INDEX_NAME_ENV)

    if not index_name:
        raise ValueError(f"Missing {INDEX_NAME_ENV} in .env")

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Missing OPENAI_API_KEY in .env")

    documents = read_markdown_documents()
    print(f"Documents found: {len(documents)}")

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    pc = get_pinecone_client()

    ensure_index(pc, index_name)

    index = pc.Index(index_name)

    vectors = []

    for doc in documents:
        chunks = chunk_text(doc["text"])

        for chunk_number, chunk in enumerate(chunks, start=1):
            vector_id = f"{doc['title']}-{chunk_number}-{uuid4().hex[:8]}"
            embedding = embeddings.embed_query(chunk)

            vectors.append(
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "source": doc["source"],
                        "title": doc["title"],
                        "chunk_number": chunk_number,
                        "text": chunk,
                    },
                }
            )

    print(f"Vectors prepared: {len(vectors)}")

    index.upsert(vectors=vectors, namespace=NAMESPACE)

    stats = index.describe_index_stats()
    print("Pinecone ingestion complete.")
    print(stats)


if __name__ == "__main__":
    main()