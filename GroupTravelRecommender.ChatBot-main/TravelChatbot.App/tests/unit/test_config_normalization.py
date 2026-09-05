import pytest
from config import Settings, ConfigurationError
from services.normalization import normalize_place, parse_rules, is_confirmation


@pytest.mark.parametrize("alias,expected", [
    ("Huế", "hue"), ("Hội An", "hoi an"), ("Hanoi", "ha noi"),
    ("Hà Nội", "ha noi"), ("Saigon", "ho chi minh city"), ("HCMC", "ho chi minh city")])
def test_vietnamese_aliases(alias, expected):
    assert normalize_place(alias) == expected


@pytest.mark.parametrize("query,price", [
    ("Find historical tours in Hue under 700000 VND", 700000),
    ("Tour Huế dưới 700.000 VND", 700000),
    ("Tours under 700k", 700000)])
def test_price_constraints(query, price):
    parsed = parse_rules(query)
    assert parsed.max_price == price
    assert not parsed.price_inclusive


def test_configuration_has_no_secret_repr():
    assert "sensitive-test-value" not in repr(Settings(openai_api_key="sensitive-test-value"))


def test_missing_env():
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        Settings.from_env({})


@pytest.mark.parametrize("field,value", [("RAG_CHUNK_OVERLAP", "2000"), ("RAG_MIN_SCORE", "nan"),
                                       ("EMBEDDING_BATCH_SIZE", "0"), ("DEMO_MODE", "maybe")])
def test_invalid_configuration(field, value):
    with pytest.raises(ConfigurationError):
        Settings.from_env({"DEMO_MODE": "true", field: value})


def test_exact_confirmation_only():
    assert is_confirmation("confirm booking")
    assert not is_confirmation("yes")
    assert not is_confirmation("I might confirm booking later")
    assert not is_confirmation("don't confirm booking")
