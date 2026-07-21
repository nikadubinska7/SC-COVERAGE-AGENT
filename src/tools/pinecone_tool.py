import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone


INDEX_NAME_ENV = "PINECONE_INDEX_NAME"
NAMESPACE = "coverage_rules"
EMBEDDING_MODEL = "text-embedding-3-small"


def get_pinecone_index():
    load_dotenv()

    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv(INDEX_NAME_ENV)

    if not api_key:
        raise ValueError("Missing PINECONE_API_KEY in .env")

    if not index_name:
        raise ValueError(f"Missing {INDEX_NAME_ENV} in .env")

    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


def retrieve_reporting_rules(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    if not query:
        raise ValueError("query is required")

    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Missing OPENAI_API_KEY in .env")

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    query_vector = embeddings.embed_query(query)

    index = get_pinecone_index()

    result = index.query(
        vector=query_vector,
        top_k=top_k,
        namespace=NAMESPACE,
        include_metadata=True,
    )

    matches = []

    for match in result.get("matches", []):
        metadata = match.get("metadata", {}) or {}

        matches.append(
            {
                "score": match.get("score"),
                "title": metadata.get("title"),
                "source": metadata.get("source"),
                "chunk_number": metadata.get("chunk_number"),
                "text": metadata.get("text"),
            }
        )

    return matches


if __name__ == "__main__":
    results = retrieve_reporting_rules(
        "How is coverage percentage calculated and which statuses are included?",
        top_k=3,
    )

    print(f"Results returned: {len(results)}")

    for idx, result in enumerate(results, start=1):
        print("")
        print(f"Result {idx}")
        print(f"Score: {result['score']}")
        print(f"Title: {result['title']}")
        print(f"Source: {result['source']}")
        print(result["text"][:700])