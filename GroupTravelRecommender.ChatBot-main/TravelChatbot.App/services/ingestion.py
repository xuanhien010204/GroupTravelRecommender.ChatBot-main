"""Offline indexing: stable IDs, complete-document marker, no cloud deletes."""
import hashlib
import logging
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from config import ConfigurationError
from services.normalization import normalize_place
from utilities.pdf_reader import chunk_text, extract_pages

log = logging.getLogger(__name__)


@dataclass
class IngestionReport:
    documents_scanned: int = 0
    documents_processed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    vectors_upserted: int = 0
    skipped: int = 0
    failed: int = 0


def document_chunks(tour, data, settings):
    fingerprint = hashlib.sha256(data).hexdigest()
    prefix = hashlib.sha256((tour["tourId"] + ":" + tour["heritageGuide"]).encode()).hexdigest()[:24]
    signature = f"{settings.rag_chunk_size}:{settings.rag_chunk_overlap}:" + settings.openai_text_embeded_deployment_name
    generation = hashlib.sha256((fingerprint + signature).encode()).hexdigest()[:24]
    chunks = []
    for page in extract_pages(data):
        for text in chunk_text(page["text"], settings.rag_chunk_size, settings.rag_chunk_overlap):
            index = len(chunks)
            chunk_id = f"{prefix}:{generation}:{index}"
            chunks.append({"id": chunk_id, "metadata": {
                "chunk_id": chunk_id, "tour_id": tour["tourId"], "tourId": tour["tourId"],
                "place": normalize_place(tour["place"]),
                "document_name": PurePosixPath(tour["heritageGuide"]).name,
                "source_key": tour["heritageGuide"], "page": page["page"],
                "chunk_index": index, "type": "heritage_guide", "version": "1",
                "content_hash": fingerprint, "document_id": prefix,
                "signature": signature, "raw_text": text}})
    # Section is omitted: plain PDF extraction cannot reliably infer headings.
    return prefix, fingerprint, chunks


def ingest(tours, documents, embeddings, vectors, settings, reindex=False):
    report = IngestionReport()
    for tour in tours:
        key = tour.get("heritageGuide")
        if not key:
            continue
        report.documents_scanned += 1
        try:
            if key.startswith(("https://", "http://")):
                raise ValueError("heritageGuide must be an S3 object key")
            data = documents.read(key)
            prefix, fingerprint, chunks = document_chunks(tour, data, settings)
            marker_id = f"manifest:{prefix}"
            existing = vectors.fetch([marker_id]).get(marker_id)
            metadata = existing.metadata if existing and hasattr(existing, "metadata") else (
                existing.get("metadata", {}) if existing else {})
            signature = f"{settings.rag_chunk_size}:{settings.rag_chunk_overlap}:" + settings.openai_text_embeded_deployment_name
            if not reindex and metadata.get("content_hash") == fingerprint and metadata.get("signature") == signature:
                report.skipped += 1
                continue
            if not chunks:
                raise ValueError("No extractable text; scanned PDFs need OCR before ingestion")
            report.chunks_created += len(chunks)
            marker_vector = None
            for offset in range(0, len(chunks), settings.embedding_batch_size):
                batch = chunks[offset:offset + settings.embedding_batch_size]
                values = embeddings.embed([chunk["metadata"]["raw_text"] for chunk in batch])
                if len(values) != len(batch):
                    raise ValueError("Incomplete embedding batch")
                report.embeddings_generated += len(values)
                payload = [dict(chunk, values=value) for chunk, value in zip(batch, values)]
                vectors.upsert(payload)
                report.vectors_upserted += len(payload)
                marker_vector = values[0]
            vectors.upsert([{"id": marker_id, "values": marker_vector, "metadata": {
                "type": "ingestion_manifest", "content_hash": fingerprint, "signature": signature}}])
            report.documents_processed += 1
        except Exception as exc:
            report.failed += 1
            log.warning("ingestion_document_failed error_type=%s", type(exc).__name__)
            if isinstance(exc, ConfigurationError) or getattr(exc, "status_code", None) in {401, 403}:
                break
    return asdict(report)
