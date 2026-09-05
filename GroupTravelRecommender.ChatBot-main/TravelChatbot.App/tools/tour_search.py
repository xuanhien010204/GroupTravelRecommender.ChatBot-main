"""Compatibility search entry points. Ingestion lives in scripts/ingest.py."""
from services.backend import default_backend
from services.normalization import parse_rules


def search_tours(query, type=None, place=None, pagination_token=None, page_size=10):
    from tools.tour_tools import build_tools
    return build_tools(default_backend())["get_tours"].invoke({
        "search_query": query, "place": place, "pagination_token": pagination_token,
        "page_size": page_size})


def search_tour_heritage(query, place, pagination_token=None, page_size=8):
    from tools.tour_tools import build_tools
    return build_tools(default_backend())["get_heritage_guide"].invoke({
        "search_query": query, "place": place, "pagination_token": pagination_token,
        "page_size": page_size})
