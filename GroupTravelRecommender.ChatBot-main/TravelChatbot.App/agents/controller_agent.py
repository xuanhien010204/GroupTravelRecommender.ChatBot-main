"""Explicit workflow: each turn runs understand -> one route -> compose -> END."""
import logging
import time
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from models.state import TravelState
from services.backend import create_backend
from services.normalization import fold, is_cancel, is_confirmation, normalize_place, parse_rules, phone_number
from services.planning import build_itinerary, rank_tours, reduce_day
from services.rag import safe_markdown
from services.repository import validate_phone
from tools.tour_tools import build_tools

log = logging.getLogger(__name__)


def date_label(timestamp):
    return datetime.fromtimestamp(timestamp, timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")


class ControllerAgent:
    def __init__(self, backend=None, checkpointer=None):
        self.backend = backend or create_backend()
        self.thread_id = str(uuid4())
        graph = StateGraph(TravelState)
        graph.add_node("understand_query", self._safe(self._understand))
        routes = {
            "tour_search": self._search, "tour_details": self._details,
            "heritage_rag": self._heritage, "group_planner": self._group,
            "itinerary_update": self._itinerary, "registered_tours": self._registered,
            "booking": self._booking, "out_of_domain": self._out_of_domain,
            "cancel": self._cancel, "error": self._error}
        for name, node in routes.items():
            graph.add_node(name, self._safe(node))
            graph.add_edge(name, "compose_answer")
        graph.add_node("compose_answer", self._compose)
        graph.add_edge(START, "understand_query")
        graph.add_conditional_edges("understand_query", lambda s: s["current_intent"], {k: k for k in routes})
        graph.add_edge("compose_answer", END)
        self.graph = graph.compile(checkpointer=checkpointer or InMemorySaver())

    def _safe(self, node):
        def guarded(state):
            try:
                return node(state)
            except Exception as exc:
                log.warning("node=%s error_type=%s", node.__name__, type(exc).__name__)
                return {"current_intent": "error", "error": "service_unavailable",
                        "answer": "A travel service is unavailable. Please try again. No booking success is assumed.",
                        "retrieved_sources": [], "grounded": False, "abstained": True,
                        "pending_action": None, "booking_context": {}}
        return guarded

    def invoke(self, initial_state=None, thread_id=None):
        return self.graph.invoke(initial_state or {},
            config={"configurable": {"thread_id": thread_id or self.thread_id}, "recursion_limit": 8})

    def chat(self, text, thread_id=None):
        if not text.strip() or len(text) > 6000:
            raise ValueError("Please enter between 1 and 6000 characters")
        started = time.perf_counter()
        result = self.invoke({"messages": [HumanMessage(content=text)]}, thread_id)
        log.info("intent=%s total_ms=%.0f", result["current_intent"], (time.perf_counter() - started) * 1000)
        return result

    def _understand(self, state):
        text = state["messages"][-1].content
        reset = {"error": None, "answer": "", "retrieved_sources": [],
                 "grounded": False, "abstained": False, "confirmation_received": False}
        if is_cancel(text):
            return {**reset, "current_intent": "cancel"}
        if is_confirmation(text):
            return {**reset, "current_intent": "booking", "confirmation_received": True, "query": {}}
        rules = parse_rules(text, state)
        # A phone-only follow-up completes details, never confirms the action.
        if state.get("pending_action") and phone_number(text) and rules.intent == "out_of_domain":
            rules.intent = "booking"
            rules.phone_number = phone_number(text)
        query = self.backend.language.understand(text, state)
        data = query.model_dump(exclude_none=True)
        explicit = rules.model_dump(exclude_none=True)
        for key, value in explicit.items():
            if key not in {"intent", "semantic_query", "price_inclusive"}:
                data[key] = value
        if rules.max_price is not None:
            data["price_inclusive"] = rules.price_inclusive
        # Contact information must be supplied by the user, never inferred by an LLM.
        data["phone_number"] = rules.phone_number
        if rules.intent != "out_of_domain":
            data["intent"] = rules.intent
        place = normalize_place(data.get("place") or state.get("current_place"))
        changed = bool(place and place != state.get("current_place"))
        profile = {} if changed else dict(state.get("group_preferences", {}))
        for key in ("people", "days", "budget_per_person", "interests", "pace"):
            if data.get(key) is not None:
                profile[key] = data[key]
        if place:
            profile["destination"] = place
        constraints = {} if changed else dict(state.get("constraints", {}))
        for key in ("max_price", "start_date", "status"):
            if data.get(key) is not None:
                constraints[key] = data[key]
        if data.get("max_price") is not None:
            constraints["price_inclusive"] = data.get("price_inclusive", False)
        if place:
            constraints["place"] = place
        result = {**reset, "query": data, "current_intent": data["intent"],
                  "current_place": place, "group_preferences": profile, "constraints": constraints}
        if changed:
            result.update(candidate_tours=[], selected_tour=None, current_itinerary=[])
        reference = self._selected({**state, "query": data})
        pending_tour = state.get("booking_context", {}).get("tour", {})
        different_target = reference and pending_tour and reference["tourId"] != pending_tour.get("tourId")
        if changed or different_target or data["intent"] not in {"booking", "tour_details", "heritage_rag"}:
            result.update(pending_action=None, booking_context={})
        return result

    def _selected(self, state):
        query = state.get("query", {})
        if query.get("tour_id"):
            return self.backend.repository.get(query["tour_id"])
        index = query.get("selected_index")
        if index is not None:
            tours = state.get("candidate_tours", [])
            return tours[index - 1] if index <= len(tours) else None
        text = fold(state["messages"][-1].content)
        named = [tour for tour in state.get("candidate_tours", [])
                 if len(tour["title"].split(" - ")[0]) > 5 and fold(tour["title"].split(" - ")[0]) in text]
        if len(named) == 1:
            return named[0]
        return state.get("selected_tour")

    def _search(self, state):
        constraints = dict(state["constraints"])
        if state["query"].get("tour_id"):
            constraints["tour_id"] = state["query"]["tour_id"]
        tours = self.backend.repository.search(constraints)
        interests = state["query"].get("interests", [])
        if interests:
            try:
                evidence = self.backend.rag.retrieve(state["query"]["semantic_query"], state.get("current_place"))
            except Exception as exc:
                log.warning("semantic_ranking_unavailable error_type=%s", type(exc).__name__)
                evidence = []
            tours = rank_tours(tours, {"interests": interests}, evidence)
        return {"candidate_tours": tours, "selected_tour": None,
                "answer": self._tour_summary(tours)}

    def _tour_summary(self, tours):
        if not tours:
            return "No tours match these constraints. Try another destination or budget."
        return "\n\n".join(f'{i}. {safe_markdown(t["title"])} | {t["price"]:,} VND/person | '
                          f'{date_label(t["startDate"])} UTC+7 | {safe_markdown(t.get("status", ""))}'
                          for i, t in enumerate(tours[:10], 1))

    def _details(self, state):
        tour = self._selected(state)
        if not tour:
            return {"answer": "Please select a tour from the results first.", "selected_tour": None}
        current = self.backend.repository.get(tour["tourId"])
        if not current:
            return {"answer": "This tour is no longer available.", "selected_tour": None}
        return {"selected_tour": current, "answer": self._tour_summary([current])}

    def _heritage(self, state):
        tour = self._selected(state)
        query = state["query"].get("semantic_query") or state["messages"][-1].content
        if tour:
            query = f'{query}. Tour: {tour["title"]}'
        matches = self.backend.rag.retrieve(query, state.get("current_place"),
                                            tour_id=tour["tourId"] if tour else None)
        answer = self.backend.rag.answer(query, matches)
        return {"answer": answer["answer"], "retrieved_sources": answer["sources"],
                "selected_tour": tour, "grounded": answer["grounded"], "abstained": answer["abstained"]}

    def _group(self, state):
        profile = state["group_preferences"]
        if not state.get("current_place"):
            return {"answer": "Which destination should I use for your group?"}
        constraints = dict(state["constraints"])
        if profile.get("budget_per_person") is not None:
            constraints.update(max_price=profile["budget_per_person"], price_inclusive=True)
        tours = self.backend.repository.search(constraints)
        query = state["query"].get("semantic_query") or "heritage and group activities"
        matches = self.backend.rag.retrieve(query, state["current_place"])
        ranked = rank_tours(tours, profile, matches)
        itinerary = build_itinerary(ranked, profile)
        answer = self.backend.rag.answer(query, matches)
        cost = sum(a["estimated_cost"] for a in itinerary)
        text = (f'Proposed plan for {profile.get("people", 1)} people, {profile.get("days", 1)} days '
                f'in {state["current_place"]}. Pace: {profile.get("pace", "balanced")}. '
                f'Tour subtotal: {cost:,} VND/person; {cost * profile.get("people", 1):,} VND/group. '
                "Meals, transport and unverified tickets are not included. Times are suggestions; "
                "check actual tour dates and duration before booking.\n\n" +
                self._tour_summary(ranked) + "\n\nHeritage evidence:\n\n" + answer["answer"])
        return {"candidate_tours": ranked, "current_itinerary": itinerary,
                "selected_tour": None, "answer": text, "retrieved_sources": answer["sources"],
                "grounded": answer["grounded"], "abstained": answer["abstained"]}

    def _itinerary(self, state):
        query = state["query"]
        day, limit = query.get("itinerary_day"), query.get("activity_limit")
        itinerary = state.get("current_itinerary", [])
        if not day or not limit or not any(a["day"] == day for a in itinerary):
            return {"answer": "Choose a day in the current itinerary and the number of activities to keep."}
        updated = reduce_day(itinerary, day, limit)
        return {"current_itinerary": updated,
                "answer": f"Day {day} now has {sum(a['day'] == day for a in updated)} activities. Other days are unchanged."}

    def _registered(self, state):
        phone = state["query"].get("phone_number")
        if not phone:
            return {"answer": "Please provide the phone number used for registration."}
        rows = build_tools(self.backend)["get_registered_tours"].invoke({"phoneNumber": phone})
        titles = [row.get("tourDetails") for row in rows if row.get("tourDetails")]
        return {"registered_tours": rows, "answer": self._tour_summary(titles) if rows else "No registrations found."}

    def _booking(self, state):
        context = dict(state.get("booking_context", {}))
        if state.get("confirmation_received"):
            if state.get("pending_action") != "REGISTER_TOUR" or not context.get("ready"):
                return {"answer": "No complete booking is awaiting confirmation. Select a tour and provide your phone number first."}
            if time.time() - context.get("created_at", 0) > 600:
                return {"pending_action": None, "booking_context": {}, "answer": "Confirmation expired. Please request the booking again."}
            result = build_tools(self.backend, approved_booking=context)["register_tour"].invoke(
                {"tourId": context["tour"]["tourId"], "phoneNumber": context["phone"]})
            error = result.get("error")
            labels = {"already_registered": "This phone number is already registered for this tour.",
                      "tour_changed": "Tour details changed. Request the booking again to review them.",
                      "tour_unavailable": "This tour is not currently bookable.",
                      "tour_not_found": "This tour no longer exists."}
            return {"pending_action": None, "booking_context": {},
                    "answer": labels.get(error, "Booking could not be completed.") if error else
                    ("DEMO simulation: " if self.backend.settings.demo_mode else "") + "Tour registration confirmed."}
        explicit_target = state["query"].get("selected_index") or state["query"].get("tour_id")
        tour = self._selected(state) or (context.get("tour") if not explicit_target else None)
        if not tour:
            return {"answer": "Select a specific tour to book, for example: Book the first tour.",
                    "pending_action": None, "booking_context": {}}
        tour = self.backend.repository.get(tour["tourId"])
        if not tour:
            return {"answer": "Tour not found.", "pending_action": None, "booking_context": {}}
        phone = state["query"].get("phone_number") or context.get("phone")
        if phone:
            validate_phone(phone)
        context = {"tour": tour, "phone": phone, "ready": bool(phone), "created_at": time.time()}
        summary = (f'Review booking: {safe_markdown(tour["title"])} ({safe_markdown(tour["tourId"])}), '
                   f'{tour["price"]:,} VND/person, {date_label(tour["startDate"])} to '
                   f'{date_label(tour["endDate"])} UTC+7, status: {safe_markdown(tour.get("status", ""))}.')
        summary += (f' Phone ending {phone[-4:]}. Reply "confirm booking" or use the confirmation button.'
                    if phone else " Please provide your phone number. Confirmation will be requested next.")
        return {"pending_action": "REGISTER_TOUR", "booking_context": context,
                "selected_tour": tour, "answer": summary}

    def _cancel(self, state):
        return {"pending_action": None, "booking_context": {}, "answer": "Pending booking cancelled."}

    def _out_of_domain(self, state):
        return {"answer": "I help with Vietnam travel, heritage, group itineraries and tour registrations. Please ask a travel question."}

    def _error(self, state):
        return {}

    def _compose(self, state):
        return {"messages": [AIMessage(content=state.get("answer") or "Please clarify your travel request.")]}
