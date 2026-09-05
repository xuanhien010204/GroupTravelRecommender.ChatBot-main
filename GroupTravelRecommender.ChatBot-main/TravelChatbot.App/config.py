"""Validated settings; imports never contact cloud services."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = False
    openai_api_key: str = field(default="", repr=False)
    openai_endpoint: str = ""
    openai_deployment_name: str = ""
    openai_text_embeded_api_key: str = field(default="", repr=False)
    openai_text_embeded_deployment_name: str = ""
    openai_api_mode: str = "azure"
    openai_api_version: str = "2024-10-21"
    pinecone_api_key: str = field(default="", repr=False)
    pinecone_heritage_index: str = "tour-heritage-guides"
    pinecone_namespace: str = "heritage-v1"
    aws_access_key_id: str = field(default="", repr=False)
    aws_secret_access_key: str = field(default="", repr=False)
    aws_session_token: str = field(default="", repr=False)
    aws_region: str = ""
    heritage_guide_s3_bucket: str = ""
    tours_table: str = "Tours"
    user_tours_table: str = "UserTours"
    bookable_statuses: str = "available,active,open"
    rag_chunk_size: int = 1800
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8
    rag_min_score: float = 0.65
    rag_context_chunks: int = 5
    embedding_batch_size: int = 32
    embedding_dimension: int = 0
    llm_temperature: float = 0.0
    api_timeout_seconds: float = 30.0
    api_max_attempts: int = 3
    max_pdf_bytes: int = 20_000_000
    source_link_ttl: int = 900

    @classmethod
    def from_env(cls, environ=None):
        if environ is None:
            load_dotenv(ROOT / ".env", override=False)
            environ = os.environ
        values = {}
        defaults = cls()
        for name in cls.__dataclass_fields__:
            raw = environ.get(name.upper())
            if raw is None or not raw.strip():
                continue
            default = getattr(defaults, name)
            try:
                if isinstance(default, bool):
                    if raw.lower() not in {"true", "false", "1", "0"}:
                        raise ValueError()
                    values[name] = raw.lower() in {"true", "1"}
                else:
                    values[name] = type(default)(raw.strip())
            except ValueError:
                raise ConfigurationError(f"Invalid value for {name.upper()}") from None
        settings = cls(**values)
        settings.validate()
        return settings

    def validate(self):
        if not 0 <= self.rag_chunk_overlap < self.rag_chunk_size <= 8000:
            raise ConfigurationError("Require 0 <= RAG_CHUNK_OVERLAP < RAG_CHUNK_SIZE <= 8000")
        bounds = {"rag_top_k": (1, 100), "rag_context_chunks": (1, 20),
                  "embedding_batch_size": (1, 128), "api_max_attempts": (1, 5),
                  "api_timeout_seconds": (1, 120), "embedding_dimension": (0, 65536),
                  "source_link_ttl": (60, 3600), "max_pdf_bytes": (1024, 100_000_000)}
        for key, (minimum, maximum) in bounds.items():
            if not minimum <= getattr(self, key) <= maximum:
                raise ConfigurationError(f"{key.upper()} must be between {minimum} and {maximum}")
        if not -1 <= self.rag_min_score <= 1 or not 0 <= self.llm_temperature <= 2:
            raise ConfigurationError("Invalid RAG_MIN_SCORE or LLM_TEMPERATURE")
        if self.openai_api_mode not in {"azure", "compatible"}:
            raise ConfigurationError("OPENAI_API_MODE must be azure or compatible")
        if self.demo_mode:
            return
        required = ("openai_api_key", "openai_endpoint", "openai_deployment_name",
                    "openai_text_embeded_api_key", "openai_text_embeded_deployment_name",
                    "pinecone_api_key", "aws_region", "heritage_guide_s3_bucket")
        missing = [name.upper() for name in required if not getattr(self, name)]
        if missing:
            raise ConfigurationError("Missing environment variables: " + ", ".join(missing))
        endpoint = urlparse(self.openai_endpoint)
        if endpoint.scheme != "https" or not endpoint.netloc or endpoint.username or endpoint.query:
            raise ConfigurationError("OPENAI_ENDPOINT must be HTTPS without credentials/query")
        if self.openai_api_mode == "azure" and endpoint.path.strip("/"):
            raise ConfigurationError("Azure mode requires the resource root; use compatible for /openai/v1/")
        if bool(self.aws_access_key_id) != bool(self.aws_secret_access_key):
            raise ConfigurationError("Set both AWS keys, or use an IAM role")


def validate_config():
    Settings.from_env()
    return True
