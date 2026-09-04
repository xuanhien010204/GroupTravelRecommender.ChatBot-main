"""Lazy, bounded adapters. No infrastructure provisioning or import-time network."""
import json
import logging
import time
from functools import cached_property

from config import ConfigurationError
from models.state import Query

log = logging.getLogger(__name__)


class ServiceUnavailable(RuntimeError):
    pass


def retry_call(fn, attempts=3, sleep=time.sleep):
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:
            status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            transient = isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in {
                "APITimeoutError", "APIConnectionError", "ReadTimeout", "ConnectTimeout"}
            transient = transient or status == 429 or (isinstance(status, int) and 500 <= status <= 599)
            if not transient or attempt == attempts - 1:
                raise
            sleep(min(2 ** attempt, 4))


def openai_client(settings, embedding=False):
    from openai import AzureOpenAI, OpenAI
    kwargs = {"api_key": settings.openai_text_embeded_api_key if embedding else settings.openai_api_key,
              "timeout": settings.api_timeout_seconds, "max_retries": 0}
    if settings.openai_api_mode == "azure":
        return AzureOpenAI(azure_endpoint=settings.openai_endpoint,
                           api_version=settings.openai_api_version, **kwargs)
    return OpenAI(base_url=settings.openai_endpoint, **kwargs)


class Language:
    def __init__(self, settings, client=None):
        self.settings = settings
        self._client = client

    @cached_property
    def client(self):
        return self._client or openai_client(self.settings)

    def json(self, system, payload):
        start = time.perf_counter()
        try:
            response = retry_call(lambda: self.client.chat.completions.create(
                model=self.settings.openai_deployment_name,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                temperature=self.settings.llm_temperature,
                response_format={"type": "json_object"}),
                self.settings.api_max_attempts)
            return json.loads(response.choices[0].message.content)
        finally:
            log.info("llm_latency_ms=%.0f", (time.perf_counter() - start) * 1000)

    def understand(self, text, state):
        schema = Query.model_json_schema()
        context = {key: state.get(key) for key in
                   ("current_place", "group_preferences", "candidate_tours", "selected_tour",
                    "constraints", "current_itinerary")}
        return Query.model_validate(self.json(
            "Extract a travel request as JSON matching this schema: " + json.dumps(schema) +
            ". You are responsible for understanding meaning: intent, destination, interests, "
            "travel_party and pace, in Vietnamese or English, including indirect phrasing. "
            "Use conversation context for references and follow-ups. "
            "A turn that only adjusts soft preferences on an existing trip - who is "
            "travelling ('di voi gia dinh', 'with my partner'), what matters more "
            "('uu tien do an hon lich su'), or how packed the trip should be "
            "('muon chill hon') - is intent refine_preferences, not a new search: it refines "
            "the existing profile. Put anything explicitly deprioritised in "
            "deprioritized_interests and order interests by how strongly they are preferred. "
            "Set only explicitly mentioned preferences; do not invent price, dates, phone "
            "numbers, tour IDs or interests, and never infer a travel_party that the user "
            "did not state. Normalize semantic_query to the meaning of the request. "
            "Unrelated requests are out_of_domain. You cannot confirm bookings.",
            {"query": text, "context": context}))


class Embeddings:
    def __init__(self, settings, client=None):
        self.settings, self._client = settings, client

    @cached_property
    def client(self):
        return self._client or openai_client(self.settings, embedding=True)

    def embed(self, texts):
        vectors = []
        size = self.settings.embedding_batch_size
        for offset in range(0, len(texts), size):
            batch = texts[offset:offset + size]
            response = retry_call(lambda: self.client.embeddings.create(
                model=self.settings.openai_text_embeded_deployment_name, input=batch),
                self.settings.api_max_attempts)
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise ServiceUnavailable("Embedding batch cardinality mismatch")
            vectors.extend(item.embedding for item in data)
        dims = {len(vector) for vector in vectors}
        if len(dims) > 1 or (dims and self.settings.embedding_dimension and
                            dims != {self.settings.embedding_dimension}):
            raise ConfigurationError("Embedding output dimension does not match EMBEDDING_DIMENSION")
        return vectors


class VectorStore:
    def __init__(self, settings, client=None):
        self.settings, self._client = settings, client

    @cached_property
    def client(self):
        if self._client is not None:
            return self._client
        from pinecone import Pinecone
        return Pinecone(api_key=self.settings.pinecone_api_key)

    @cached_property
    def description(self):
        return retry_call(lambda: self.client.describe_index(self.settings.pinecone_heritage_index),
                          self.settings.api_max_attempts)

    @cached_property
    def index(self):
        desc = self.description
        if str(getattr(desc.metric, "value", desc.metric)) != "cosine":
            raise ConfigurationError("Heritage index must use cosine for RAG_MIN_SCORE")
        return self.client.Index(host=desc.host)

    def validate_dimension(self, vector):
        dimension = int(self.description.dimension)
        if len(vector) != dimension:
            raise ConfigurationError(f"Embedding dimension {len(vector)} != index dimension {dimension}")

    def query(self, vector, filters, top_k):
        self.validate_dimension(vector)
        response = retry_call(lambda: self.index.query(
            namespace=self.settings.pinecone_namespace, vector=vector, top_k=top_k,
            filter=filters, include_metadata=True, timeout=self.settings.api_timeout_seconds),
            self.settings.api_max_attempts)
        matches = [{"id": m.id, "score": float(m.score), "metadata": dict(m.metadata or {})}
                   for m in response.matches]
        marker_ids = list({"manifest:" + m["metadata"]["document_id"] for m in matches
                           if m["metadata"].get("document_id")})
        manifests = self.fetch(marker_ids) if marker_ids else {}
        active = []
        for match in matches:
            md = match["metadata"]
            marker = manifests.get("manifest:" + md.get("document_id", ""))
            manifest = marker.metadata if marker and hasattr(marker, "metadata") else {}
            if (manifest.get("content_hash") == md.get("content_hash") and
                    manifest.get("signature") == md.get("signature") and marker):
                active.append(match)
        return active

    def fetch(self, ids):
        response = retry_call(lambda: self.index.fetch(
            namespace=self.settings.pinecone_namespace, ids=ids, timeout=self.settings.api_timeout_seconds),
            self.settings.api_max_attempts)
        return response.vectors

    def upsert(self, vectors):
        for vector in vectors:
            self.validate_dimension(vector["values"])
        retry_call(lambda: self.index.upsert(vectors=vectors, namespace=self.settings.pinecone_namespace,
                                            timeout=self.settings.api_timeout_seconds),
                   self.settings.api_max_attempts)


def aws_session(settings):
    import boto3
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs.update(aws_access_key_id=settings.aws_access_key_id,
                      aws_secret_access_key=settings.aws_secret_access_key)
    if settings.aws_session_token:
        kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.Session(**kwargs)


class Documents:
    def __init__(self, settings, client=None):
        self.settings, self._client = settings, client

    @cached_property
    def client(self):
        from botocore.config import Config
        return self._client or aws_session(self.settings).client("s3", config=Config(
            connect_timeout=10, read_timeout=self.settings.api_timeout_seconds,
            retries={"mode": "standard", "total_max_attempts": self.settings.api_max_attempts}))

    def read(self, key):
        response = self.client.get_object(Bucket=self.settings.heritage_guide_s3_bucket, Key=key)
        body = response["Body"]
        try:
            if response.get("ContentLength", 0) > self.settings.max_pdf_bytes:
                raise ValueError("PDF exceeds MAX_PDF_BYTES")
            data = body.read(self.settings.max_pdf_bytes + 1)
            if len(data) > self.settings.max_pdf_bytes:
                raise ValueError("PDF exceeds MAX_PDF_BYTES")
            return data
        finally:
            body.close()

    def link(self, key):
        if not key or key.startswith(("https://", "http://")):
            return None
        return self.client.generate_presigned_url("get_object",
            Params={"Bucket": self.settings.heritage_guide_s3_bucket, "Key": key},
            ExpiresIn=self.settings.source_link_ttl)
