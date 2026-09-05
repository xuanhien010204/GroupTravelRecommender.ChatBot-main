"""Streamlit presentation layer; a session owns its controller and graph thread."""
import logging
import streamlit as st
from config import ConfigurationError, Settings
from agents.controller_agent import ControllerAgent, date_label
from services.backend import create_backend

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
st.set_page_config(page_title="Common Ground | Travel Copilot", page_icon=":compass:", layout="wide")
st.markdown("""
<style>
:root { --sand:#f5f1e7; --ink:#183f3a; --rust:#ac553b; }
.stApp { background:radial-gradient(ellipse at 90% 0%,#e3ebdf 0,transparent 45%),var(--sand); color:var(--ink); }
h1,h2,h3 { font-family:Georgia,'Times New Roman',serif!important; letter-spacing:-.025em; }
h1 { font-size:3.5rem!important; }
[data-testid="stSidebar"] { background:#e9e4d7; border-right:1px solid #d2ccbc; }
[data-testid="stChatMessage"] { background:rgba(255,255,255,.65); border:1px solid #dedace; }
[data-testid="stMetric"] { border-top:2px solid #ac553b; padding-top:.5rem; }
.stButton>button[kind="primary"] { background:#23594e; border:0; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:12px; }
@keyframes arrive { from { opacity:0; transform:translateY(6px); } to {opacity:1;transform:none;} }
[data-testid="stChatMessage"] { animation:arrive .25s ease-out; }
@media(prefers-reduced-motion:reduce) { * {animation:none!important;} }
@media(max-width:700px) { h1 {font-size:2.3rem!important;} }
</style>
""", unsafe_allow_html=True)
st.caption("COMMON GROUND / AI GROUP TRAVEL COPILOT")
st.title("Different interests. One shared journey.")
st.write("Build a trip around your people, with tour facts and heritage evidence you can inspect.")

try:
    settings = Settings.from_env()
except ConfigurationError as exc:
    st.error(str(exc))
    st.info("Fill .env using .env.example, or set DEMO_MODE=true in your shell to explore the synthetic demo.")
    st.stop()

if "controller" not in st.session_state:
    st.session_state.controller = ControllerAgent(create_backend(settings))
    st.session_state.result = {}
controller = st.session_state.controller
state = st.session_state.result

if settings.demo_mode:
    st.warning("OFFLINE DEMO: synthetic tours, prices, dates and document fixtures. No cloud calls or real bookings.")

with st.sidebar:
    st.subheader("Trip Profile")
    profile = state.get("group_preferences", {})
    st.write("Destination", profile.get("destination", "Not selected"))
    left, right = st.columns(2)
    left.metric("People", profile.get("people", "-"))
    right.metric("Days", profile.get("days", "-"))
    budget = profile.get("budget_per_person")
    st.write("Budget / person", f"{budget:,} VND" if budget is not None else "Not set")
    st.write("Interests", ", ".join(profile.get("interests", [])) or "Not set")
    st.write("Pace", profile.get("pace", "Not set"))
    st.caption("Tell the chat who is travelling; preferences update as the conversation develops.")
    if st.button("New trip", use_container_width=True):
        st.session_state.controller = ControllerAgent(create_backend(settings))
        st.session_state.result = {}
        st.rerun()
    st.divider()
    st.caption("Sources support history. DynamoDB supports prices and availability. Proposed times are not verified opening hours.")
    if settings.demo_mode:
        st.caption("Graph memory and simulated bookings last for this browser session.")

chat, details = st.columns([1.25, 1], gap="large")
trigger = None
with chat:
    st.subheader("Plan together")
    if not state.get("messages"):
        st.info("Try the group scenario, then ask to simplify a day or explain a recommendation.")
        if st.button("Try the Hue group scenario", type="primary"):
            trigger = ("We are 4 people visiting Hue for 2 days. Budget is about 800000 VND/person. "
                       "Two people like history, one likes food, and we want a relaxed schedule.")
    for message in state.get("messages", []):
        role = "user" if message.type == "human" else "assistant"
        with st.chat_message(role):
            if role == "user":
                st.text(message.content)
            else:
                st.markdown(message.content)
    context = state.get("booking_context", {})
    if state.get("pending_action") == "REGISTER_TOUR":
        with st.container(border=True):
            st.subheader("Review your booking")
            st.write(context.get("tour", {}).get("title", "Select a tour"))
            st.caption("Only this exact target will be registered after confirmation.")
            confirm, cancel = st.columns(2)
            if confirm.button("Confirm booking", type="primary", disabled=not context.get("ready")):
                trigger = "confirm booking"
            if cancel.button("Cancel booking"):
                trigger = "cancel booking"

with details:
    tours_tab, plan_tab, source_tab = st.tabs(["Tour shortlist", "Itinerary", "Sources"])
    with tours_tab:
        tours = state.get("candidate_tours", [])
        if not tours:
            st.caption("Tours matching your destination and budget will appear here.")
        for index, tour in enumerate(tours[:20], 1):
            with st.container(border=True):
                st.caption(f'OPTION {index:02} / {tour["place"]}')
                st.subheader(tour["title"])
                st.write(f'{tour["price"]:,} VND / person')
                st.caption(f'{date_label(tour["startDate"])} UTC+7 | {tour.get("status", "")}')
                if st.button("Review booking", key="book_" + tour["tourId"]):
                    trigger = f'Book tour id {tour["tourId"]}'
        if len(tours) > 20:
            st.caption("Showing 20 options. Refine destination, budget or date for a smaller shortlist.")
    with plan_tab:
        itinerary = state.get("current_itinerary", [])
        st.caption("Suggested slots only. Verify tour dates/duration. Meals and transport are excluded from subtotal.")
        if itinerary:
            st.metric("Tour subtotal / person", f'{sum(a["estimated_cost"] for a in itinerary):,} VND')
        for day in sorted({activity["day"] for activity in itinerary}):
            st.subheader(f"Day {day}")
            for activity in (a for a in itinerary if a["day"] == day):
                with st.container(border=True):
                    st.write(activity["time"], activity["activity"])
                    st.caption(activity["reason"])
                    st.caption(f'{activity["estimated_cost"]:,} VND | {activity["source"]}')
        if itinerary and st.button("Keep only two places on Day 1"):
            trigger = "Day 1 is too busy. Keep only two places."
    with source_tab:
        for source in state.get("retrieved_sources", []):
            md = source["metadata"]
            with st.container(border=True):
                st.write(f'[{source["citation"]}] {md["document_name"]}')
                if md.get("page"):
                    st.caption(f'PDF page {int(md["page"])}')
                st.caption(f'Relevance score: {source["score"]:.3f}')
                st.text(md["raw_text"])
                if source.get("url"):
                    st.link_button("Open source document", source["url"])
        if not state.get("retrieved_sources"):
            st.caption("No cited heritage evidence for the current answer.")

prompt = st.chat_input("Describe your group, explore heritage, or refine your itinerary")
if prompt or trigger:
    with st.spinner("Checking your trip context and evidence..."):
        try:
            st.session_state.result = controller.chat(prompt or trigger)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
    st.rerun()
