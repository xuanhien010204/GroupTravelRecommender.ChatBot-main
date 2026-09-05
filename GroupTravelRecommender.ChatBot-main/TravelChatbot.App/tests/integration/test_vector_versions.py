from types import SimpleNamespace as NS
from unittest.mock import Mock
from config import Settings
from services.cloud import VectorStore


def test_only_completed_document_generation_is_retrieved():
    client, index = Mock(), Mock()
    client.describe_index.return_value = NS(dimension=2, host="fixture", metric="cosine")
    client.Index.return_value = index
    common = {"document_id": "doc", "signature": "settings"}
    index.query.return_value = NS(matches=[
        NS(id="old", score=0.99, metadata=dict(common, content_hash="old")),
        NS(id="current", score=0.9, metadata=dict(common, content_hash="new")),
        NS(id="partial", score=0.8, metadata=dict(common, content_hash="incomplete"))])
    index.fetch.return_value = NS(vectors={
        "manifest:doc": NS(metadata={"content_hash": "new", "signature": "settings"})})
    store = VectorStore(Settings(demo_mode=True), client)
    matches = store.query([1, 0], {"place": {"$eq": "hue"}}, 8)
    assert [match["id"] for match in matches] == ["current"]
    assert index.query.call_args.kwargs["filter"] == {"place": {"$eq": "hue"}}
    client.create_index.assert_not_called()
    index.delete.assert_not_called()
