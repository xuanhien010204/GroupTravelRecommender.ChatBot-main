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
from services.messages import (CONSTRAINT_LABELS, INTEREST_LABELS, PACE_WORDS_ONLY,
                               detect_language, label, money, preference_summary, t)
from services.normalization import (fold, is_cancel, is_confirmation, normalize_place,
                                    parse_rules, phone_number)
from services.planning import (blocking_constraints, build_itinerary, closest_tours,
                               ranked_with_reasons, reduce_day, tradeoffs)
from services.preferences import has_soft_preference, merge_interests
from services.rag import safe_markdown
from services.repository import validate_phone
from tools.tour_tools import build_tools

log = logging.getLogger(__name__)

# Hard constraints: they filter, they are never relaxed without the user saying so.
HARD_FIELDS = ("max_price", "start_date", "status")
# Soft preferences: they only reorder and explain results.
SOFT_FIELDS = ("interests", "travel_party", "pace")
# Facts and actions a regular expression reads more reliably than a language model.
# Everything else - intent, destination, interests, party, pace - is the model's job.
EXACT_FIELDS = ("tour_id", "selected_index", "max_price", "start_date")
EXACT_INTENTS = {"booking", "registered_tours", "itinerary_update"}


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
            "refine_preferences": self._refine,
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
                language = (detect_language(state["messages"][-1].content)
                            if state.get("messages") else None) or state.get("language") or "en"
                return {"current_intent": "error", "error": "service_unavailable",
                        "answer": t("service_unavailable", language),
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
        language = detect_language(text) or state.get("language") or "en"
        reset = {"error": None, "answer": "", "retrieved_sources": [], "language": language,
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
        # The model owns meaning; regular expressions only override exact facts and actions.
        for key in EXACT_FIELDS:
            if explicit.get(key) is not None:
                data[key] = explicit[key]
        if rules.max_price is not None:
            data["price_inclusive"] = rules.price_inclusive
        # Contact information must be supplied by the user, never inferred by an LLM.
        data["phone_number"] = rules.phone_number
        if rules.intent in EXACT_INTENTS:
            data["intent"] = rules.intent
            for key in ("activity_limit", "itinerary_day"):
                if explicit.get(key) is not None:
                    data[key] = explicit[key]
        data.setdefault("intent", "out_of_domain")
        place = normalize_place(data.get("place") or state.get("current_place"))
        changed = bool(place and place != state.get("current_place"))
        # A new destination invalidates hard constraints tied to it and the shortlist,
        # but who is travelling and what they enjoy carries over to the next search.
        profile = dict(state.get("group_preferences", {}))
        if changed:
            profile = {key: value for key, value in profile.items() if key in SOFT_FIELDS}
        for key in ("people", "days", "budget_per_person", "travel_party", "pace"):
            if data.get(key) is not None:
                profile[key] = data[key]
        if data.get("interests") or data.get("deprioritized_interests"):
            profile["interests"] = merge_interests(profile.get("interests"),
                                                   data.get("interests") or [],
                                                   data.get("deprioritized_interests") or [])
        if place:
            profile["destination"] = place
        constraints = {} if changed else dict(state.get("constraints", {}))
        for key in HARD_FIELDS:
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

    def _evidence(self, state, query=None):
        """Retrieved heritage passages used as semantic signal. Never fails the turn."""
        try:
            return self.backend.rag.retrieve(query or state["query"].get("semantic_query")
                                             or state["messages"][-1].content,
                                             state.get("current_place"))
        except Exception as exc:
            log.warning("semantic_ranking_unavailable error_type=%s", type(exc).__name__)
            return []

    def _recommend(self, state):
        """Hard filters -> candidate tours -> semantic and preference ranking."""
        language = state.get("language", "en")
        profile = dict(state.get("group_preferences", {}))
        constraints = dict(state["constraints"])
        if state["query"].get("tour_id"):
            constraints["tour_id"] = state["query"]["tour_id"]
        tours = self.backend.repository.search(constraints)
        if not tours:
            return {"candidate_tours": [], "selected_tour": None,
                    "answer": self._no_results(constraints, language)}
        # Rank whenever any semantic preference exists, not only for a few interests.
        evidence = self._evidence(state) if has_soft_preference(profile) else []
        ranked = ranked_with_reasons(tours, profile, evidence)
        return {"candidate_tours": [row["tour"] for row in ranked], "selected_tour": None,
                "answer": self._ranked_summary(ranked, profile, language)}

    def _search(self, state):
        return self._recommend(state)

    def _refine(self, state):
        """Update the trip profile in place and rebuild the existing recommendation."""
        language = state.get("language", "en")
        profile = state.get("group_preferences", {})
        prefs = preference_summary(profile, language)
        if not state["constraints"].get("place"):
            return {"answer": t("prefs_noted_need_destination", language, prefs=prefs) if prefs
                    else t("need_destination", language)}
        result = self._recommend(state)
        result["answer"] = t("refined", language, prefs=prefs) + "\n\n" + result["answer"]
        if state.get("current_itinerary") and result["candidate_tours"]:
            result["current_itinerary"] = build_itinerary(result["candidate_tours"], profile)
        return result

    def _tour_line(self, index, tour, language):
        return (f'{index}. {safe_markdown(tour["title"])} | '
                f'{money(tour["price"], language)} {t("per_person", language)} | '
                f'{date_label(tour["startDate"])} UTC+7 | {safe_markdown(tour.get("status", ""))}')

    def _ranked_summary(self, ranked, profile, language):
        """List tours with the reasons the data actually supports."""
        lines = []
        for index, row in enumerate(ranked[:10], 1):
            line = self._tour_line(index, row["tour"], language)
            reasons = [label(INTEREST_LABELS, name, language) for name in row["reasons"]]
            budget = profile.get("budget_per_person")
            if budget and row["tour"]["price"] <= budget:
                reasons.append(t("budget_fit", language))
            if reasons:
                line += f'\n   - {t("why_prefix", language)}: ' + ", ".join(reasons)
            lines.append(line)
        return "\n\n".join(lines)

    def _tour_summary(self, tours, language="en"):
        if not tours:
            return t("zero_results_none", language)
        return "\n\n".join(self._tour_line(index, tour, language)
                           for index, tour in enumerate(tours[:10], 1))

    def _no_results(self, constraints, language):
        """Explain the empty result and offer the closest options; relax nothing silently."""
        kept = [key for key in ("place",) + HARD_FIELDS if constraints.get(key) is not None]
        described = ", ".join(f'{label(CONSTRAINT_LABELS, key, language)} '
                              f'({self._constraint_value(key, constraints[key], language)})'
                              for key in kept)
        parts = [t("zero_results_head", language, kept=described or "-")]
        try:
            catalogue = self.backend.repository.search({})
        except Exception as exc:
            log.warning("fallback_catalogue_unavailable error_type=%s", type(exc).__name__)
            catalogue = []
        blocking = blocking_constraints(catalogue, constraints)
        names = [label(CONSTRAINT_LABELS, key, language) for key in (blocking or kept)]
        if names:
            parts.append(t("zero_results_blocking" if len(blocking) == 1
                           else "zero_results_blocking_many", language,
                           blocking=", ".join(names)))
        nearest = closest_tours(catalogue, constraints) if catalogue else []
        if nearest:
            parts.append(t("zero_results_closest", language))
            parts.append("\n\n".join(
                self._tour_line(index, tour, language) + "\n   - " +
                "; ".join(self._tradeoff_text(item, constraints, language)
                          for item in tradeoffs(tour, constraints))
                for index, tour in enumerate(nearest, 1)))
        else:
            parts.append(t("zero_results_none", language))
        parts.append(t("zero_results_no_relax", language))
        parts.append(self._clarification(blocking or kept, nearest, constraints, language))
        return "\n\n".join(part for part in parts if part)

    def _constraint_value(self, key, value, language):
        if key == "max_price":
            return f'{money(value, language)} VND'
        if key == "start_date":
            return date_label(value)
        return str(value).title() if key == "place" else str(value)

    def _tradeoff_text(self, item, constraints, language):
        key, value = item
        if key == "max_price":
            return t("tradeoff_price", language, amount=money(value, language))
        if key == "start_date":
            return t("tradeoff_date", language, date=date_label(value))
        if key == "place":
            return t("tradeoff_place", language, place=str(value).title(),
                     wanted=str(constraints.get("place", "")).title())
        return t("tradeoff_status", language, status=value or "-")

    def _clarification(self, keys, nearest, constraints, language):
        """Exactly one question, aimed at the constraint that is actually in the way."""
        if "max_price" in keys and nearest:
            cheapest = min(nearest, key=lambda tour: tour["price"])
            if cheapest["price"] > constraints.get("max_price", 0):
                return t("ask_relax_budget", language, amount=money(cheapest["price"], language))
        if "start_date" in keys and nearest:
            latest = max(nearest, key=lambda tour: tour["startDate"])
            return t("ask_relax_date", language, date=date_label(latest["startDate"]))
        if "place" in keys:
            return t("ask_relax_place", language)
        if "status" in keys:
            return t("ask_relax_status", language)
        return t("ask_relax_generic", language)

    def _details(self, state):
        language = state.get("language", "en")
        tour = self._selected(state)
        if not tour:
            return {"answer": t("select_tour_first", language), "selected_tour": None}
        current = self.backend.repository.get(tour["tourId"])
        if not current:
            return {"answer": t("tour_gone", language), "selected_tour": None}
        return {"selected_tour": current, "answer": self._tour_summary([current], language)}

    def _heritage(self, state):
        language = state.get("language", "en")
        tour = self._selected(state)
        query = state["query"].get("semantic_query") or state["messages"][-1].content
        if tour:
            query = f'{query}. Tour: {tour["title"]}'
        matches = self.backend.rag.retrieve(query, state.get("current_place"),
                                            tour_id=tour["tourId"] if tour else None)
        answer = self.backend.rag.answer(query, matches, language)
        return {"answer": answer["answer"], "retrieved_sources": answer["sources"],
                "selected_tour": tour, "grounded": answer["grounded"], "abstained": answer["abstained"]}

    def _group(self, state):
        language = state.get("language", "en")
        profile = state["group_preferences"]
        if not state.get("current_place"):
            return {"answer": t("need_destination", language)}
        constraints = dict(state["constraints"])
        if profile.get("budget_per_person") is not None:
            constraints.update(max_price=profile["budget_per_person"], price_inclusive=True)
        tours = self.backend.repository.search(constraints)
        query = state["query"].get("semantic_query") or "heritage and group activities"
        matches = self.backend.rag.retrieve(query, state["current_place"])
        if not tours:
            return {"candidate_tours": [], "selected_tour": None,
                    "answer": self._no_results(constraints, language)}
        ranked = ranked_with_reasons(tours, profile, matches)
        tours = [row["tour"] for row in ranked]
        itinerary = build_itinerary(tours, profile)
        answer = self.backend.rag.answer(query, matches, language)
        cost = sum(a["estimated_cost"] for a in itinerary)
        people = profile.get("people", 1)
        text = (t("plan_intro", language, people=people, days=profile.get("days", 1),
                  place=str(state["current_place"]).title(),
                  pace=label(PACE_WORDS_ONLY, profile.get("pace", "balanced"), language),
                  cost=money(cost, language), unit=t("per_person", language),
                  total=money(cost * people, language)) + " " +
                t("plan_disclaimer", language) + "\n\n" +
                self._ranked_summary(ranked, profile, language) +
                f'\n\n{t("heritage_heading", language)}:\n\n' + answer["answer"])
        return {"candidate_tours": tours, "current_itinerary": itinerary,
                "selected_tour": None, "answer": text, "retrieved_sources": answer["sources"],
                "grounded": answer["grounded"], "abstained": answer["abstained"]}

    def _itinerary(self, state):
        language = state.get("language", "en")
        query = state["query"]
        day, limit = query.get("itinerary_day"), query.get("activity_limit")
        itinerary = state.get("current_itinerary", [])
        if not day or not limit or not any(a["day"] == day for a in itinerary):
            return {"answer": t("itinerary_needs_day", language)}
        updated = reduce_day(itinerary, day, limit)
        return {"current_itinerary": updated,
                "answer": t("itinerary_updated", language, day=day,
                            count=sum(a["day"] == day for a in updated))}

    def _registered(self, state):
        language = state.get("language", "en")
        phone = state["query"].get("phone_number")
        if not phone:
            return {"answer": t("need_phone", language)}
        rows = build_tools(self.backend)["get_registered_tours"].invoke({"phoneNumber": phone})
        titles = [row.get("tourDetails") for row in rows if row.get("tourDetails")]
        return {"registered_tours": rows,
                "answer": self._tour_summary(titles, language) if rows
                else t("no_registrations", language)}

    def _booking(self, state):
        language = state.get("language", "en")
        context = dict(state.get("booking_context", {}))
        if state.get("confirmation_received"):
            if state.get("pending_action") != "REGISTER_TOUR" or not context.get("ready"):
                return {"answer": t("booking_none_pending", language)}
            if time.time() - context.get("created_at", 0) > 600:
                return {"pending_action": None, "booking_context": {},
                        "answer": t("booking_expired", language)}
            result = build_tools(self.backend, approved_booking=context)["register_tour"].invoke(
                {"tourId": context["tour"]["tourId"], "phoneNumber": context["phone"]})
            error = result.get("error")
            keys = {"already_registered": "booking_duplicate", "tour_changed": "booking_changed",
                    "tour_unavailable": "booking_unavailable", "tour_not_found": "booking_missing"}
            return {"pending_action": None, "booking_context": {},
                    "answer": t(keys.get(error, "booking_failed"), language) if error else
                    ("DEMO simulation: " if self.backend.settings.demo_mode else "") +
                    t("booking_confirmed", language)}
        explicit_target = state["query"].get("selected_index") or state["query"].get("tour_id")
        tour = self._selected(state) or (context.get("tour") if not explicit_target else None)
        if not tour:
            return {"answer": t("booking_pick_tour", language),
                    "pending_action": None, "booking_context": {}}
        tour = self.backend.repository.get(tour["tourId"])
        if not tour:
            return {"answer": t("booking_missing", language),
                    "pending_action": None, "booking_context": {}}
        phone = state["query"].get("phone_number") or context.get("phone")
        if phone:
            validate_phone(phone)
        context = {"tour": tour, "phone": phone, "ready": bool(phone), "created_at": time.time()}
        summary = t("booking_review", language, title=safe_markdown(tour["title"]),
                    tour_id=safe_markdown(tour["tourId"]), price=money(tour["price"], language),
                    unit=t("per_person", language), start=date_label(tour["startDate"]),
                    end=date_label(tour["endDate"]), status=safe_markdown(tour.get("status", "")))
        summary += " " + (t("booking_ask_confirm", language, digits=phone[-4:]) if phone
                          else t("booking_ask_phone", language))
        return {"pending_action": "REGISTER_TOUR", "booking_context": context,
                "selected_tour": tour, "answer": summary}

    def _cancel(self, state):
        return {"pending_action": None, "booking_context": {},
                "answer": t("booking_cancelled", state.get("language", "en"))}

    def _out_of_domain(self, state):
        return {"answer": t("out_of_domain", state.get("language", "en"))}

    def _error(self, state):
        return {}

    def _compose(self, state):
        return {"messages": [AIMessage(content=state.get("answer")
                                       or t("clarify", state.get("language", "en")))]}
