from unittest.mock import Mock
import pytest
from models.state import Query
from tools.tour_tools import build_tools

GROUP = ("We are 4 people visiting Hue for 2 days. Budget is about 800000 VND/person. "
         "Two people like history, one likes food, and we prefer a relaxed trip.")


def test_search_by_place(agent):
    state = agent.chat("Find tours in Hue")
    assert state["candidate_tours"]
    assert {t["place"] for t in state["candidate_tours"]} == {"Hue"}


def test_price_filter(agent):
    state = agent.chat("Find tours in Hue under 180000 VND")
    assert [t["price"] for t in state["candidate_tours"]] == [150000]


def test_followup_context_and_pronoun(agent):
    first = agent.chat("Find tours in Hue")
    second = first["candidate_tours"][1]
    price = agent.chat("How much is the second one?")
    assert price["selected_tour"]["tourId"] == second["tourId"]
    assert f'{second["price"]:,}' in price["answer"]
    heritage = agent.chat("What is special about it?")
    assert heritage["selected_tour"]["tourId"] == second["tourId"]
    assert heritage["retrieved_sources"]
    assert all(s["metadata"]["tour_id"] == second["tourId"] for s in heritage["retrieved_sources"])
    assert len(heritage["messages"]) == 6


def test_heritage_rag(agent):
    state = agent.chat("Why choose Thien Mu Pagoda in Hue for history?")
    assert state["grounded"]
    assert "Sources:" in state["answer"]
    assert state["retrieved_sources"][0]["metadata"]["source_key"]


def test_negative_rag(agent):
    state = agent.chat("Are there Egyptian pyramids in Quy Nhon?")
    assert state["abstained"]
    assert state["retrieved_sources"] == []


def test_group_preferences_and_total_budget(agent):
    state = agent.chat(GROUP)
    profile = state["group_preferences"]
    assert profile["people"] == 4 and profile["days"] == 2
    assert profile["budget_per_person"] == 800000
    assert profile["interests"] == ["history", "food"]
    assert profile["pace"] == "relaxed"
    assert state["current_itinerary"]
    assert sum(a["estimated_cost"] for a in state["current_itinerary"]) <= 800000
    assert state["retrieved_sources"]


def test_itinerary_followup_only_changes_requested_day(agent):
    state = agent.chat(GROUP.replace("relaxed", "balanced"))
    other_day = [a for a in state["current_itinerary"] if a["day"] != 1]
    result = agent.chat("Day 1 is too busy. Keep only two places.")
    assert len([a for a in result["current_itinerary"] if a["day"] == 1]) == 2
    assert [a for a in result["current_itinerary"] if a["day"] != 1] == other_day


def test_booking_without_confirmation(agent, backend):
    agent.chat("Find tours in Hue")
    state = agent.chat("Book the first tour for 0900000000")
    assert state["pending_action"] == "REGISTER_TOUR"
    assert not backend.repository.bookings
    agent.chat("yes")
    assert not backend.repository.bookings


def test_booking_with_confirmation_and_duplicate(agent, backend):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    result = agent.chat("confirm booking")
    assert "confirmed" in result["answer"]
    assert len(backend.repository.bookings) == 1
    agent.chat("Book the first tour for 0900000000")
    result = agent.chat("confirm booking")
    assert "already registered" in result["answer"]
    assert len(backend.repository.bookings) == 1


def test_phone_followup_requires_another_turn_for_confirmation(agent, backend):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour")
    result = agent.chat("confirm booking")
    assert "No complete booking" in result["answer"]
    state = agent.chat("0900000000")
    assert state["booking_context"]["ready"]
    assert not backend.repository.bookings
    agent.chat("confirm booking")
    assert len(backend.repository.bookings) == 1


def test_context_switch_clears_pending_booking(agent, backend):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    agent.chat("Find tours in Hoi An")
    state = agent.chat("confirm booking")
    assert not backend.repository.bookings
    assert "No complete booking" in state["answer"]


def test_direct_tool_cannot_authorize_itself(backend):
    result = build_tools(backend)["register_tour"].invoke(
        {"tourId": "demo-01", "phoneNumber": "0900000000"})
    assert result["error"] == "confirmation_required"
    assert not backend.repository.bookings


def test_out_of_domain(agent):
    state = agent.chat("Write a sorting algorithm in Python")
    assert state["current_intent"] == "out_of_domain"


def test_pinecone_failure_is_safe(agent, backend):
    backend.rag.vectors.query = Mock(side_effect=RuntimeError("SECRET stack trace"))
    state = agent.chat("Heritage in Hue")
    assert state["error"] == "service_unavailable"
    assert "SECRET" not in state["answer"]
    assert not state["retrieved_sources"]


def test_llm_failure_is_safe(agent, backend):
    backend.language.understand = Mock(side_effect=TimeoutError("SECRET"))
    state = agent.chat("Find tours in Hue")
    assert state["error"] == "service_unavailable"
    assert "SECRET" not in state["answer"]


def test_threads_are_isolated(agent):
    agent.chat("Find tours in Hue", thread_id="a")
    result = agent.chat("How much is the second one?", thread_id="b")
    assert not result.get("selected_tour")
    assert not result.get("candidate_tours")


def test_registered_tours(agent):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    agent.chat("confirm booking")
    state = agent.chat("Get registered tours for 0900000000")
    assert len(state["registered_tours"]) == 1
