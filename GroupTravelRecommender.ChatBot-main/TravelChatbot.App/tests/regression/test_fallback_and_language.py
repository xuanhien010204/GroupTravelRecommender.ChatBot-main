"""Zero-result behaviour and answering in the user's language."""
import pytest

from services.messages import detect_language
from services.planning import blocking_constraints, closest_tours, tradeoffs


def test_zero_results_is_never_a_bare_refusal(agent):
    state = agent.chat("Find tours in Hue under 100000 VND")
    assert state["candidate_tours"] == []
    answer = state["answer"]
    assert answer != "No tours match these constraints. Try another destination or budget."
    assert "No tours match these constraints." not in answer
    # It explains the blocking constraint, offers alternatives and asks one question.
    assert "budget" in answer
    assert "Thien Mu Pagoda" in answer
    assert answer.count("?") == 1


def test_zero_results_preserves_hard_constraints(agent):
    state = agent.chat("Find tours in Hue under 100000 VND")
    assert state["constraints"]["max_price"] == 100000
    assert state["constraints"]["place"] == "hue"
    assert "I will not change your budget, dates or destination on my own." in state["answer"]


def test_zero_results_offers_the_cheapest_step_up_as_a_question(agent):
    state = agent.chat("Find tours in Hue under 100000 VND")
    assert "raise the budget to 150,000 VND/person" in state["answer"]


def test_zero_results_names_the_blocking_constraint(backend):
    catalogue = backend.repository.search({})
    constraints = {"place": "hue", "max_price": 100000, "price_inclusive": False}
    assert blocking_constraints(catalogue, constraints) == ["max_price"]


def test_closest_candidates_keep_the_requested_destination(backend):
    catalogue = backend.repository.search({})
    constraints = {"place": "hue", "max_price": 100000, "price_inclusive": False}
    nearest = closest_tours(catalogue, constraints)
    assert nearest and all(tour["place"] == "Hue" for tour in nearest)
    assert tradeoffs(nearest[0], constraints) == [("max_price", 50000)]


def test_impossible_destination_asks_a_clarification(agent):
    state = agent.chat("Find tours in Quy Nhon")
    assert state["candidate_tours"] == []
    assert "destination" in state["answer"]
    assert state["answer"].count("?") == 1


def test_zero_results_answers_in_vietnamese(agent):
    state = agent.chat("Tìm tour ở Huế dưới 100.000 VND")
    assert state["language"] == "vi"
    answer = state["answer"]
    assert "Chưa có tour nào thỏa mãn" in answer
    assert "ngân sách" in answer
    assert "Mình sẽ không tự ý thay đổi" in answer
    assert detect_language(answer) == "vi"


@pytest.mark.parametrize("text", ["Tìm tour ở Huế", "đi với gia đình", "muốn chill hơn"])
def test_vietnamese_input_gets_vietnamese_answer(agent, text):
    agent.chat("Tìm tour ở Huế")
    state = agent.chat(text)
    assert state["language"] == "vi"
    assert detect_language(state["answer"]) == "vi"


def test_english_input_keeps_english_answer(agent):
    state = agent.chat("Find tours in Hue")
    assert state["language"] == "en"
    assert "VND/person" in state["answer"]


def test_language_switches_with_the_user(agent):
    assert agent.chat("Tìm tour ở Huế")["language"] == "vi"
    assert agent.chat("Find tours in Hue")["language"] == "en"


def test_vietnamese_out_of_domain_reply(agent):
    state = agent.chat("Viết cho mình một thuật toán sắp xếp")
    assert state["current_intent"] == "out_of_domain"
    assert detect_language(state["answer"]) == "vi"


def test_a_bare_phone_number_does_not_switch_language(agent):
    """A reply with no words carries no language signal; keep the user's language."""
    agent.chat("Tìm tour ở Huế")
    agent.chat("đặt tour thứ nhất")
    state = agent.chat("0912345678")
    assert state["language"] == "vi"
    assert state["booking_context"]["ready"]
    assert "Xem lại thông tin đặt tour" in state["answer"]


def test_vietnamese_booking_flow_stays_vietnamese(agent, backend):
    agent.chat("Tìm tour ở Huế")
    state = agent.chat("đặt tour thứ nhất, số điện thoại 0900000000")
    assert state["pending_action"] == "REGISTER_TOUR"
    assert "Xem lại thông tin đặt tour" in state["answer"]
    result = agent.chat("xác nhận đặt tour")
    assert "Đã xác nhận đăng ký tour." in result["answer"]
    assert len(backend.repository.bookings) == 1
