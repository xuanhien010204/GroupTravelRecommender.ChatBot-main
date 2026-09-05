from dataclasses import dataclass
from functools import lru_cache
from config import Settings
from services.cloud import Documents, Embeddings, Language, VectorStore
from services.rag import HeritageRAG
from services.repository import TourRepository


@dataclass
class Backend:
    settings: Settings
    repository: object
    rag: object
    language: object


def create_backend(settings=None):
    settings = settings or Settings.from_env()
    if settings.demo_mode:
        from services.demo import demo_backend
        return demo_backend(settings)
    language = Language(settings)
    return Backend(settings, TourRepository(settings),
                   HeritageRAG(settings, Embeddings(settings), VectorStore(settings),
                               language, Documents(settings)), language)


@lru_cache(maxsize=1)
def default_backend():
    return create_backend()
