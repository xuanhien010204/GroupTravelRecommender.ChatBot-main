from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any, Optional
from config import (
    OPENAI_ENDPOINT,
    OPENAI_TEXT_EMBEDED_API_KEY,
    OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME,
    PINECONE_API_KEY,
    PINECONE_ENVIRONMENT,
)
import re
from openai import OpenAI

# Initialize OpenAI client for embeddings (Azure OpenAI wrapper)
openai_client = OpenAI(
    api_key=OPENAI_TEXT_EMBEDED_API_KEY,
    base_url=OPENAI_ENDPOINT,
)

# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

# Get or create index for tours
TOURS_INDEX = "tours"
TOUR_HERITAGE_INDEX = "tour-heritage-guides"
indexes = [idx.name for idx in pc.list_indexes()]

if TOURS_INDEX not in indexes:
    pc.create_index(
        name=TOURS_INDEX,
        dimension=1536,  # OpenAI embedding dimension
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=PINECONE_ENVIRONMENT
        ),
    )

if TOUR_HERITAGE_INDEX not in indexes:
    pc.create_index(
        name=TOUR_HERITAGE_INDEX,
        dimension=1536,  # OpenAI embedding dimension
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region=PINECONE_ENVIRONMENT
        ),
    )

# Index instance
tour_index = pc.Index(TOURS_INDEX)
tour_heritage_index = pc.Index(TOUR_HERITAGE_INDEX)

def embed_tours(tours: List[Dict[str, Any]]) -> None:
    """
    Embed tour information into Pinecone. Skip tours that already have vectors in the index.

    Args:
        tours: list of tour dicts (each must include "tourId")
    """
    # Collect tour ids
    tour_ids = [t["tourId"] for t in tours if t.get("tourId")]
    if not tour_ids:
        return

    # Fetch existing vectors to avoid re-embedding
    existing = tour_index.fetch(ids=tour_ids)
    existing_ids = set(existing.vectors.keys())

    # Filter tours that need embedding
    new_tours = [t for t in tours if t.get("tourId") and t["tourId"] not in existing_ids]
    if not new_tours:
        return

    vectors_to_upsert: List[Dict[str, Any]] = []
    for tour in new_tours:
        # Ensure a type for filtering
        tour["type"] = "tour_info"
        search_text = f"Tour in {tour.get('place','')}: {tour.get('title','')}. Price: {tour.get('price','')} VND"

        # Get embedding from Azure OpenAI
        resp = openai_client.embeddings.create(
            input=search_text,
            model=OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME,
        )
        embedding = resp.data[0].embedding

        vectors_to_upsert.append({
            "id": tour["tourId"],
            "values": embedding,
            "metadata": tour,
        })

    # Upsert in batches
    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i : i + batch_size]
        tour_index.upsert(vectors=batch)


def search_tours(
    query: str,
    type: Optional[str] = None,
    place: Optional[str] = None,
    pagination_token: Optional[str] = None,
    page_size: int = 10,
) -> Dict[str, Any]:
    """
    Search tours using a natural language query.

    Args:
        query: The search query string
        type: Optional type to filter results
        place: Optional place name to filter results
        pagination_token: Token for pagination
        page_size: Number of results per page

    Returns a dict with keys:
      - results: list of metadata dicts
      - next_token: pagination token or None
    """
    # If query explicitly asks for a tourId, return that vector's metadata
    tour_id_match = re.search(r"(?:tour ?id|id)[:\s]+([a-zA-Z0-9-]+)", query, re.IGNORECASE)
    if tour_id_match:
        tour_id = tour_id_match.group(1)
        fetched = tour_index.fetch(ids=[tour_id])
        if fetched and fetched.get("vectors", {}).get(tour_id):
            return {"results": [fetched["vectors"][tour_id]["metadata"]], "next_token": None}
        return {"results": [], "next_token": None}

    # Build metadata filter
    filter_dict: Dict[str, Any] = {}
    if type:
        filter_dict["type"] = {"$eq": type}
    
    # Place filter
    if place:
        filter_dict["place"] = {"$eq": place}

    # Price filter support (e.g., "under 600000 VND")
    price_match = re.search(r"under\s+(\d+(?:,\d{3})*)\s*(?:vnd|VND)?", query, re.IGNORECASE)
    if price_match:
        price_str = price_match.group(1).replace(",", "")
        max_price = int(price_str)
        filter_dict["price"] = {"$lt": max_price}

    query_text = query

    # Get embedding for the query
    resp = openai_client.embeddings.create(
        input=query_text,
        model=OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME,
    )
    query_embedding = resp.data[0].embedding

    # Query Pinecone (uses SDK response as dict)
    results = tour_index.query(
        vector=query_embedding,
        filter=filter_dict if filter_dict else None,
        top_k=page_size,
        include_metadata=True,
        pagination_token=pagination_token,
    )

    matches = results.get("matches", [])
    return {"results": [m.get("metadata", {}) for m in matches], "next_token": results.get("pagination_token")}

def search_tour_heritage(
    query: str,
    place: str,
    pagination_token: Optional[str] = None,
    page_size: int = 10,
) -> Dict[str, Any]:
    """
    Search the tour heritage index for heritage guide chunks matching the query and filtered by tourIds.
    Args:
        query: The search query string.
        place: place metadata to filter heritage guides.
        pagination_token: Token for pagination.
        page_size: Number of results per page.
    Returns:
        Dict with 'results' (list of metadata dicts) and 'next_token'.
    """

    if not place:
        return {"results": [], "next_token": None}

    # Build metadata filter for a single tourId
    filter_dict = {"place": {"$eq": place}}

    # Get embedding for the query
    resp = openai_client.embeddings.create(
        input=query,
        model=OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME,
    )
    query_embedding = resp.data[0].embedding

    # Query Pinecone heritage index
    results = tour_heritage_index.query(
        vector=query_embedding,
        filter=filter_dict,
        top_k=page_size,
        include_metadata=True,
        pagination_token=pagination_token,
    )

    matches = results.get("matches", [])
    return {"results": [m.get("metadata", {}) for m in matches], "next_token": results.get("pagination_token")}


def heritage_chunk_exists(chunk_id: str) -> bool:
    """
    Check whether a heritage chunk vector with the given chunk_id exists in the heritage index.
    Returns True if exists, False otherwise.
    """
    if not chunk_id:
        return False
    
    try:
        fetched = tour_heritage_index.fetch(ids=[chunk_id])
        vectors = fetched.vectors
        return isinstance(vectors, dict) and chunk_id in vectors and vectors[chunk_id]

    except Exception as e:
        print("Error checking heritage chunk existence: ", e)
        return False


def embed_pdf_chunks(chunks: List[str], base_metadata: Dict[str, Any]) -> None:
    """
    Embed PDF text chunks into Pinecone. Each chunk becomes a separate vector with id
    "{tourId}_heritageGuide_{index}". Existing chunks are skipped.
    """
    if not chunks:
        return

    chunk_ids = [f"{base_metadata['tourId']}_heritageGuide_{i}" for i in range(len(chunks))]
    existing = tour_heritage_index.fetch(ids=chunk_ids)
    existing_ids = set(existing.vectors.keys())

    vectors_to_upsert: List[Dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{base_metadata['tourId']}_heritageGuide_{i}"
        if chunk_id in existing_ids:
            continue

        resp = openai_client.embeddings.create(
            input=chunk,
            model=OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME,
        )
        embedding = resp.data[0].embedding

        md = {
            "place": base_metadata.get("place"),
            "tourId": base_metadata.get("tourId"),
            "heritageGuide": base_metadata.get("heritageGuide"),
            "chunk_index": i,
            "type": "heritage_guide",
            "raw_text": chunk
        }

        vectors_to_upsert.append({"id": chunk_id, "values": embedding, "metadata": md})

    if not vectors_to_upsert:
        return

    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i : i + batch_size]
        tour_heritage_index.upsert(vectors=batch)