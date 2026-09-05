from unittest.mock import Mock
from scripts.evaluate_rag import evaluate
from services.rag import ABSTENTION


def test_metrics_are_computed_from_misses(backend):
    backend.rag.retrieve = Mock(return_value=[])
    backend.rag.answer = Mock(return_value={"answer": ABSTENTION, "sources": [],
                                            "abstained": True, "grounded": False})
    report = evaluate(backend, [{"id": "miss", "query": "question", "place": "hue",
                                "expected_sources": ["actual-fixture-id"],
                                "expected_facts": ["required fact"], "should_abstain": False}])
    assert report["metrics"]["hit_at_3"] == 0
    assert report["metrics"]["recall_at_5"] == 0
    assert report["metrics"]["grounded_answer"] == 0
    assert report["metrics"]["abstention_correct"] == 0


def test_abstention_with_citations_is_not_correct(backend):
    source = {"id": "fixture", "metadata": {}}
    backend.rag.retrieve = Mock(return_value=[source])
    backend.rag.answer = Mock(return_value={"answer": ABSTENTION, "sources": [source],
                                            "abstained": True, "grounded": False})
    report = evaluate(backend, [{"id": "bad", "query": "question",
                                "expected_sources": [], "should_abstain": True}])
    assert report["metrics"]["citation_correct"] == 0
