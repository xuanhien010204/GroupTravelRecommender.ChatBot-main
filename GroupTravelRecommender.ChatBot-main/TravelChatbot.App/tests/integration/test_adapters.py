from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock
import boto3
import pytest
from botocore.stub import Stubber
from config import Settings, ConfigurationError
from models.tour import Tour
from services.cloud import Embeddings, VectorStore, retry_call
from services.demo import fixture_tours
from services.repository import TourRepository


def test_embeddings_are_batched_and_ordered():
    client = Mock()
    client.embeddings.create.side_effect = [
        NS(data=[NS(index=1, embedding=[2.0, 0]), NS(index=0, embedding=[1.0, 0])]),
        NS(data=[NS(index=0, embedding=[3.0, 0])])]
    result = Embeddings(Settings(demo_mode=True, embedding_batch_size=2), client).embed(["a", "b", "c"])
    assert result == [[1, 0], [2, 0], [3, 0]]
    assert client.embeddings.create.call_count == 2


def test_dimension_mismatch_fails_before_query():
    client = Mock()
    client.describe_index.return_value = NS(dimension=3, host="fixture", metric="cosine")
    with pytest.raises(ConfigurationError, match="dimension"):
        VectorStore(Settings(demo_mode=True), client).query([1, 2], {}, 3)
    client.Index.assert_not_called()


@pytest.mark.parametrize("status,expected_attempts", [(429, 3), (503, 3), (401, 1), (400, 1)])
def test_bounded_retry(status, expected_attempts):
    class Error(Exception):
        status_code = status
    call, sleep = Mock(side_effect=Error()), Mock()
    with pytest.raises(Error):
        retry_call(call, attempts=3, sleep=sleep)
    assert call.call_count == expected_attempts


def test_timeout_retry_recovers():
    call = Mock(side_effect=[TimeoutError(), "ok"])
    assert retry_call(call, sleep=lambda _: None) == "ok"


def dynamo():
    return boto3.client("dynamodb", region_name="us-east-1",
                        aws_access_key_id="fixture", aws_secret_access_key="fixture")


def test_paginated_dynamodb_scan_keeps_all_rows():
    client = dynamo()
    repo = TourRepository(Settings(demo_mode=True), client)
    tours = fixture_tours()[:2]
    items = [Tour(**{k: v for k, v in t.items() if k != "synthetic"}).to_dynamodb() for t in tours]
    key = {"place": {"S": "Hue"}, "tourId": {"S": "demo-01"}}
    with Stubber(client) as stub:
        stub.add_response("scan", {"Items": items[:1], "LastEvaluatedKey": key}, {"TableName": "Tours"})
        stub.add_response("scan", {"Items": items[1:]}, {"TableName": "Tours", "ExclusiveStartKey": key})
        assert len(repo.search({"place": "Huế"})) == 2
        stub.assert_no_pending_responses()


def test_atomic_duplicate_uses_condition():
    client = Mock()
    repo = TourRepository(Settings(demo_mode=True), client)
    tour = fixture_tours()[0]
    repo.get = Mock(return_value=tour)
    from botocore.exceptions import ClientError
    client.put_item.side_effect = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
    assert repo.register(tour, "0900000000", confirmed=True)["error"] == "already_registered"
    assert "attribute_not_exists" in client.put_item.call_args.kwargs["ConditionExpression"]


def test_changed_tour_does_not_write():
    client = Mock()
    repo = TourRepository(Settings(demo_mode=True), client)
    tour = fixture_tours()[0]
    repo.get = Mock(return_value=dict(tour, price=tour["price"] + 1))
    assert repo.register(tour, "0900000000", confirmed=True)["error"] == "tour_changed"
    client.put_item.assert_not_called()
