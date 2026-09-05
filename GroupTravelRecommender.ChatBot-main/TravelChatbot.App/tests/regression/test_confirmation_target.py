def test_switching_selected_tour_cancels_previous_confirmation(agent, backend):
    agent.chat("Find tours in Hue")
    agent.chat("Book the first tour for 0900000000")
    state = agent.chat("How much is the second one?")
    assert state["pending_action"] is None
    agent.chat("confirm booking")
    assert not backend.repository.bookings
