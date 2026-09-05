"""Small deterministic rules shared by live query parsing and offline fixtures."""
import re
import unicodedata
from datetime import datetime, timezone
from models.state import Query

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
    if re.search(r"\b(book|register|reserve|dat tour|dang ky)\b", value):
        data["intent"] = "booking"
    elif re.search(r"(registered|my bookings|da dang ky|da dat)", value):
        data["intent"] = "registered_tours"
    elif re.search(r"(day \d|ngay \d).*(busy|reduce|keep|only|giam|chi|giu)", value):
        data["intent"] = "itinerary_update"
    elif re.search(r"(people|persons|nguoi|itinerary|lich trinh|\d+ days|\d+ ngay)", value):
        data["intent"] = "group_planner"
    elif re.search(r"(?:find|show|search|tim|cho toi).*(?:tours?|chuyen di)", value):
        data["intent"] = "tour_search"
    elif re.search(r"(history|heritage|special|why|pagoda|pyramid|lich su|di san|dac biet|tai sao)", value):
        data["intent"] = "heritage_rag"
    elif re.search(r"(how much|price of|bao nhieu|gia cua)", value) and state.get("candidate_tours"):
        data["intent"] = "tour_details"
    elif re.search(r"(tour|travel|du lich|under|duoi)", value) or data["place"]:
        data["intent"] = "tour_search"
    else:
        data["intent"] = "out_of_domain"
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
                         ("dau tien", 1), ("thu hai", 2), ("thu ba", 3)):
        if word in value:
            data["selected_index"] = number
    tour_id = re.search(r"(?:tour\s*id|id)\s*[:=]?\s+([a-zA-Z0-9_-]+)", text, re.I)
    if tour_id:
        data["tour_id"] = tour_id[1]
    if data["intent"] in {"booking", "registered_tours"} or state.get("pending_action"):
        data["phone_number"] = phone_number(text)
    if data["intent"] == "itinerary_update":
        limit = re.search(r"(?:only|keep|to|con|giu|chi)\s+(\d+|two|hai)", value)
        if limit:
            data["activity_limit"] = 2 if limit[1] in {"two", "hai"} else int(limit[1])
    if re.search(r"(relaxed|chill|thu gian|nhe nhang)", value):
        data["pace"] = "relaxed"
    elif re.search(r"(balanced|can bang)", value):
        data["pace"] = "balanced"
    interests = []
    for label, words in (("history", ("history", "historical", "lich su", "heritage")),
                         ("food", ("food", "cuisine", "am thuc")),
                         ("nature", ("nature", "thien nhien"))):
        if any(w in value for w in words):
            interests.append(label)
    if interests:
        data["interests"] = interests
    date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", value)
    if date:
        try:
            data["start_date"] = int(datetime.fromisoformat(date[1]).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            pass
    return Query.model_validate(data)
