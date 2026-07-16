import os
import uuid
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from google import genai

logger = logging.getLogger(__name__)

# ── Qdrant Configuration ───────────────────────────────────────────────────────
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "expense_policies"
EMBEDDING_MODEL = "gemini-embedding-2"
VECTOR_SIZE = 3072  # gemini-embedding-2 outputs 3072-dimensional vectors

# Initialize Qdrant Client (connects to running server)
try:
    client = QdrantClient(url=QDRANT_URL)
except Exception as e:
    logger.error(f"Failed to initialize QdrantClient: {e}")
    client = None

# Initialize Google GenAI Client
_api_key = os.environ.get("GEMINI_API_KEY", "")
if _api_key:
    genai_client = genai.Client(api_key=_api_key)
else:
    genai_client = None
    logger.warning("GEMINI_API_KEY not set. Qdrant RAG will fail.")

def _get_embedding(text: str) -> list[float]:
    """Helper to get embeddings from Gemini."""
    if not genai_client:
        raise ValueError("GEMINI_API_KEY is missing.")
    
    response = genai_client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
    )
    return response.embeddings[0].values

def initialize_policies(policy_text: str) -> None:
    """
    Chunks a document and stores it in a Qdrant collection named expense_policies.
    Uses Gemini text-embedding-004 for vectorization.
    """
    if not client:
        logger.error("QdrantClient not initialized.")
        return

    logger.info("Initializing policies in Qdrant...")
    
    # Recreate the collection to ensure vector dimensions match
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info(f"Created new collection: {COLLECTION_NAME}")

    # Simple semantic chunking: split by paragraphs (double newlines)
    chunks = [chunk.strip() for chunk in policy_text.split("\n\n") if chunk.strip()]
    
    points = []
    for i, chunk in enumerate(chunks):
        try:
            vector = _get_embedding(chunk)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"text": chunk, "chunk_index": i}
            )
            points.append(point)
        except Exception as e:
            logger.error(f"Failed to embed chunk {i}: {e}")

    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        logger.info(f"Upserted {len(points)} policy chunks into Qdrant.")
    else:
        logger.warning("No policy chunks were successfully embedded.")


def search_policy(query: str, top_k: int = 3) -> list[str]:
    """
    Takes a user query (like 'Uber travel limit'), embeds it, 
    and retrieves the top_k most relevant policy chunks.
    """
    if not client or not genai_client:
        logger.error("Clients not initialized.")
        return []

    try:
        query_vector = _get_embedding(query)
        
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k
        )
        
        results = [hit.payload["text"] for hit in search_result.points if hit.payload and "text" in hit.payload]
        logger.info(f"Found {len(results)} relevant policies for query: '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"Failed to search Qdrant for policy: {e}")
        return []
