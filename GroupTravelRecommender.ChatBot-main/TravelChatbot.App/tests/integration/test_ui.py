from streamlit.testing.v1 import AppTest
from config import ROOT


def test_streamlit_starts_and_group_scenario(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    app = AppTest.from_file(ROOT / "app.py", default_timeout=20).run()
    assert not app.exception
    next(b for b in app.button if b.label == "Try the Hue group scenario").click().run()
    assert not app.exception
    state = app.session_state["result"]
    assert state["group_preferences"]["people"] == 4
    assert state["current_itinerary"]
    app.chat_input[0].set_value("Day 1 is too busy. Keep only two places.").run()
    assert not app.exception
    assert "Other days are unchanged" in app.session_state["result"]["answer"]
