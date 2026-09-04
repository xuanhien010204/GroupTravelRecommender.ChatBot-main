"""Conversational refinement: soft preferences steer ranking without resetting the trip."""
import pytest

from services.preferences import party_evidence
from services.planning import party_supported


def search_hue(agent):
    return agent.chat("Find tours in Hue")


def ids(state):
    return [tour["tourId"] for tour in state["candidate_tours"]]


def test_family_followup_refines_instead_of_searching(agent):
    search_hue(agent)
    state = agent.chat("đi với gia đình")
    assert state["current_intent"] == "refine_preferences"
    assert state["group_preferences"]["travel_party"] == "family"
    # The destination and shortlist survive; the order changes.
    assert state["constraints"]["place"] == "hue"
    assert set(ids(state)) == {"demo-01", "demo-02", "demo-03", "demo-04", "demo-06", "demo-07"}


def test_family_ranking_is_supported_by_tour_data(agent):
    search_hue(agent)
    state = agent.chat("đi với gia đình")
    top = state["candidate_tours"][0]
    # Promoted only because the tour record itself names families.
    assert party_supported(top, "family")
    assert top["tourId"] == "demo-06"


def test_family_claim_is_never_invented(agent):
    """A tour without family evidence must not be described as family-suitable."""
    search_hue(agent)
    state = agent.chat("đi với gia đình")
    unsupported = [tour for tour in state["candidate_tours"]
                   if not party_evidence(tour["title"] + " " + tour["category"], "family")]
    assert unsupported
    for tour in unsupported:
        assert not party_supported(tour, "family")
    assert "gia đình" not in state["answer"].split("1.")[1]


def test_couple_followup_sets_party(agent):
    search_hue(agent)
    state = agent.chat("đi với người yêu")
    assert state["current_intent"] == "refine_preferences"
    assert state["group_preferences"]["travel_party"] == "couple"
    assert state["candidate_tours"][0]["tourId"] == "demo-07"


def test_chill_followup_sets_relaxed_pace(agent):
    search_hue(agent)
    state = agent.chat("muốn chill hơn")
    assert state["current_intent"] == "refine_preferences"
    assert state["group_preferences"]["pace"] == "relaxed"
    assert ids(state)


def test_food_over_history_reorders_and_deprioritizes(agent):
    first = agent.chat("Find historical tours in Hue")
    assert first["group_preferences"]["interests"] == ["history"]
    state = agent.chat("ưu tiên đồ ăn hơn lịch sử")
    assert state["current_intent"] == "refine_preferences"
    # Food is now the preference; history was explicitly deprioritised, so it is dropped.
    assert state["group_preferences"]["interests"] == ["food"]
    assert state["candidate_tours"][0]["tourId"] == "demo-02"


def test_children_followup_maps_to_family(agent):
    search_hue(agent)
    state = agent.chat("có trẻ nhỏ")
    assert state["current_intent"] == "refine_preferences"
    assert state["group_preferences"]["travel_party"] == "family"


def test_refinement_preserves_hard_constraints(agent):
    first = agent.chat("Find tours in Hue under 200000 VND")
    assert first["constraints"]["max_price"] == 200000
    state = agent.chat("đi với gia đình")
    assert state["constraints"]["max_price"] == 200000
    assert state["constraints"]["place"] == "hue"
    # The budget still filters after refinement; nothing above it may appear.
    assert all(tour["price"] < 200000 for tour in state["candidate_tours"])
    assert "demo-07" not in ids(state)


def test_refinement_accumulates_instead_of_resetting(agent):
    search_hue(agent)
    agent.chat("đi với gia đình")
    agent.chat("muốn chill hơn")
    state = agent.chat("ưu tiên đồ ăn hơn lịch sử")
    profile = state["group_preferences"]
    assert profile["travel_party"] == "family"
    assert profile["pace"] == "relaxed"
    assert "food" in profile["interests"]
    assert profile["destination"] == "hue"


def test_soft_preferences_survive_a_destination_change(agent):
    search_hue(agent)
    agent.chat("đi với gia đình")
    state = agent.chat("Find tours in Hoi An")
    # Who is travelling carries over; the destination-bound shortlist does not.
    assert state["group_preferences"]["travel_party"] == "family"
    assert state["constraints"]["place"] == "hoi an"
    assert {tour["place"] for tour in state["candidate_tours"]} == {"Hoi An"}


def test_refinement_without_destination_asks_for_one(agent):
    state = agent.chat("đi với gia đình")
    assert state["current_intent"] == "refine_preferences"
    assert state["group_preferences"]["travel_party"] == "family"
    assert "?" in state["answer"]
    assert not state.get("candidate_tours")


def test_refinement_does_not_disturb_a_pending_selection_target(agent):
    """Refining recommendations must clear a stale booking rather than book blindly."""
    search_hue(agent)
    agent.chat("Book the first tour for 0900000000")
    state = agent.chat("muốn chill hơn")
    assert state["pending_action"] is None
    assert state["group_preferences"]["pace"] == "relaxed"


@pytest.mark.parametrize("text,field,value", [
    ("đi với gia đình", "travel_party", "family"),
    ("đi với người yêu", "travel_party", "couple"),
    ("đi với bạn bè", "travel_party", "friends"),
    ("mình đi một mình", "travel_party", "solo"),
    ("muốn chill hơn", "pace", "relaxed"),
])
def test_vietnamese_soft_preferences(agent, text, field, value):
    search_hue(agent)
    state = agent.chat(text)
    assert state["group_preferences"][field] == value
