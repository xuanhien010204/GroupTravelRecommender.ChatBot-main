import time
from unittest.mock import Mock
from models.state import Query


def test_llm_cannot_invent_phone(agent, backend):
    agent.chat("Find tours in Hue")
    backend.language.understand = Mock(return_value=Query(intent="booking", selected_index=1,
                                                         phone_number="0999999999"))
    state = agent.chat("Book the first tour")
    assert not state["booking_context"]["ready"]
    assert state["booking_context"]["phone"] is None
    agent.chat("confirm booking")
    assert not backend.repository.bookings


def test_invalid_target_does_not_reuse_old_approval(agent, backend):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    state = agent.chat("Book tour id does-not-exist")
    assert not state["pending_action"]
    agent.chat("confirm booking")
    assert not backend.repository.bookings


def test_expired_confirmation_does_not_write(agent, backend, monkeypatch):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    now = time.time()
    monkeypatch.setattr("agents.controller_agent.time.time", lambda: now + 601)
    state = agent.chat("confirm booking")
    assert "expired" in state["answer"]
    assert not backend.repository.bookings


def test_named_site_overrides_previous_selected_tour(agent):
    agent.chat("Find tours in Hue")
    agent.chat("How much is the second one?")
    state = agent.chat("Why choose Thien Mu Pagoda?")
    assert state["selected_tour"]["tourId"] == "demo-01"


def test_semantic_tour_query_retains_price_constraint(agent, backend):
    state = agent.chat("Find historical tours in Hue under 180000 VND")
    assert state["current_intent"] == "tour_search"
    assert [tour["tourId"] for tour in state["candidate_tours"]] == ["demo-01"]
