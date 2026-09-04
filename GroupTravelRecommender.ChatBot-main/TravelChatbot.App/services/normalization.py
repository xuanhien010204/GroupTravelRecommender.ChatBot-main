"""Small deterministic rules shared by live query parsing and offline fixtures."""
import re
import unicodedata
from datetime import datetime, timezone
from models.state import Query
from services.preferences import (detect_interests, detect_pace, detect_travel_party,
                                  has_soft_preference)

ALIASES = {
    "hue": ("hue",),
    "hoi an": ("hoi an", "hoian"),
    "ha noi": ("ha noi", "hanoi"),
    "ho chi minh city": ("ho chi minh city", "ho chi minh", "hcmc", "hcm", "saigon", "sai gon"),
    "quy nhon": ("quy nhon",),
    "da nang": ("da nang", "danang"),
}


def fold(text):
    text = unicodedata.normalize("NFD", str(text).lower().replace("\u0111", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def normalize_place(place):
    value = fold(place or "")
    return next((key for key, aliases in ALIASES.items() if value in aliases), value)


def detect_place(text):
    value = fold(text)
    for key, aliases in ALIASES.items():
        if any(re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", value) for a in aliases):
            return key
    return None


def phone_number(text):
    match = re.search(r"(?<!\d)(\+?\d[\d -]{7,16}\d)(?!\d)", text)
    if not match:
        return None
    value = re.sub(r"[ -]", "", match[1])
    return value if re.fullmatch(r"\+?\d{9,15}", value) else None


def is_confirmation(text):
    return fold(text).strip(" .!") in {"confirm booking", "confirm", "yes, confirm booking",
                                      "xac nhan dat tour", "xac nhan", "dong y dat tour"}


def is_cancel(text):
    return fold(text).strip(" .!") in {"cancel", "cancel booking", "huy", "huy dat tour"}


def parse_rules(text, state=None):
    state = state or {}
    value = fold(text)
    data = {"semantic_query": text, "place": detect_place(text)}
    amount = re.search(r"(under|below|duoi|budget[^\d]{0,20}|ngan sach[^\d]{0,20}|up to|at most)\s*([\d][\d,.]*)(\s*[km])?", value)
    if amount:
        number = amount[2]
        suffix = (amount[3] or "").strip()
        if suffix:
            price = int(float(number.replace(",", ".")) * (1000 if suffix == "k" else 1_000_000))
        else:
            price = int(re.sub(r"[,.]", "", number))
        data["max_price"] = price
        data["price_inclusive"] = amount[1] not in {"under", "below", "duoi"}
        if "budget" in value or "ngan sach" in value:
            data["budget_per_person"] = price
    for field, pattern in (("people", r"(\d+)\s*(?:people|persons|nguoi)"),
                           ("days", r"(\d+)\s*(?:days|ngay)"),
                           ("itinerary_day", r"(?:day|ngay)\s*(\d+)")):
        match = re.search(pattern, value)
        if match:
            data[field] = int(match[1])
    index = re.search(r"(?:tour|one|option|thu)\s*#?(\d+)", value)
    if index:
        data["selected_index"] = int(index[1])
    for word, number in (("first", 1), ("second", 2), ("third", 3),
                         ("dau tien", 1), ("thu nhat", 1), ("thu hai", 2), ("thu ba", 3)):
        if word in value:
            data["selected_index"] = number
    tour_id = re.search(r"(?:tour\s*id|id)\s*[:=]?\s+([a-zA-Z0-9_-]+)", text, re.I)
    if tour_id:
        data["tour_id"] = tour_id[1]
    pace = detect_pace(text)
    if pace:
        data["pace"] = pace
    party = detect_travel_party(text)
    if party:
        data["travel_party"] = party
    preferred, demoted = detect_interests(text)
    if preferred:
        data["interests"] = preferred
    if demoted:
        data["deprioritized_interests"] = demoted
    date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", value)
    if date:
        try:
            data["start_date"] = int(datetime.fromisoformat(date[1]).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass
    data["intent"] = classify_intent(value, data, state)
    if data["intent"] in {"booking", "registered_tours"} or state.get("pending_action"):
        data["phone_number"] = phone_number(text)
    if data["intent"] == "itinerary_update":
        limit = re.search(r"(?:only|keep|to|con|giu|chi)\s+(\d+|two|hai)", value)
        if limit:
            data["activity_limit"] = 2 if limit[1] in {"two", "hai"} else int(limit[1])
    return Query.model_validate(data)


# A message carrying one of these is not a preference refinement: it changes the trip's
# hard constraints or names an exact target, so it is a search or an action instead.
HARD_SIGNALS = ("place", "max_price", "start_date", "status", "tour_id",
                "selected_index", "people", "days")
QUESTION = re.compile(r"[?]|\b(why|what|how|which|where|tai sao|the nao|co gi|gi dac biet)\b")


def is_refinement(value, data):
    """True when the turn only adjusts soft preferences on the existing trip profile."""
    if not has_soft_preference(data):
        return False
    if any(data.get(key) is not None for key in HARD_SIGNALS):
        return False
    return not QUESTION.search(value)


def classify_intent(value, data, state):
    if re.search(r"\b(book|register|reserve|dat tour|dang ky)\b", value):
        return "booking"
    if re.search(r"(registered|my bookings|da dang ky|da dat)", value):
        return "registered_tours"
    if re.search(r"(day \d|ngay \d).*(busy|reduce|keep|only|giam|chi|giu)", value):
        return "itinerary_update"
    if re.search(r"(\d+\s*(?:people|persons|nguoi)|itinerary|lich trinh|\d+ days|\d+ ngay)", value):
        return "group_planner"
    if re.search(r"(?:find|show|search|tim|cho toi).*(?:tours?|chuyen di)", value):
        return "tour_search"
    # Soft-preference follow-ups refine the profile; they are not fresh heritage questions.
    if is_refinement(value, data):
        return "refine_preferences"
    if re.search(r"(history|heritage|special|why|pagoda|pyramid|lich su|di san|dac biet|tai sao)", value):
        return "heritage_rag"
    if re.search(r"(how much|price of|bao nhieu|gia cua)", value) and state.get("candidate_tours"):
        return "tour_details"
    if re.search(r"(tour|travel|du lich|under|duoi)", value) or data.get("place"):
        return "tour_search"
    return "out_of_domain"
