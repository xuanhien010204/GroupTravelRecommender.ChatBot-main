"""Ranking, itinerary building and zero-result diagnosis.

Hard constraints have already been applied by the repository before anything here runs:
these functions only order candidates and explain them. A tour is never claimed to suit a
travel party or pace unless the tour record or its retrieved evidence contains that signal.
"""
from copy import deepcopy

from services.normalization import fold
from services.preferences import (interest_evidence, pace_evidence, party_evidence)

# Sum is 1.0; each component is normalised to 0..1 before weighting.
WEIGHTS = {"semantic": 0.30, "interests": 0.30, "travel_party": 0.15,
           "budget": 0.15, "pace": 0.10}


def evidence_by_tour(sources):
    """Best retrieval score per tour, plus the evidence text available for that tour."""
    scores, texts = {}, {}
    for source in sources or ():
        metadata = source.get("metadata", {})
        tour_id = metadata.get("tour_id")
        if not tour_id:
            continue
        scores[tour_id] = max(scores.get(tour_id, 0.0), float(source.get("score", 0.0)))
        texts[tour_id] = texts.get(tour_id, "") + " " + str(metadata.get("raw_text", ""))
    return scores, texts


def tour_text(tour, evidence_text=""):
    return fold(" ".join([tour.get("title", ""), tour.get("category", ""),
                          tour.get("heritageGuide", ""), evidence_text]))


def score_tour(tour, profile, semantic=None, evidence_text=""):
    """Return (total_score, reasons). ``reasons`` holds only data-supported interest labels.

    ``semantic`` is None when no retrieval evidence exists for any candidate; the component
    is then dropped rather than scored zero, so a RAG outage does not flatten the ranking.
    """
    text = tour_text(tour, evidence_text)
    parts, reasons = {}, []

    if semantic is not None:
        parts["semantic"] = max(0.0, min(1.0, semantic))

    interests = profile.get("interests") or []
    if interests:
        # Earlier interests weigh more, so "food over history" reorders rather than filters.
        weights = [1.0 / (index + 1) for index in range(len(interests))]
        earned = 0.0
        for interest, weight in zip(interests, weights):
            if interest_evidence(text, interest):
                earned += weight
                reasons.append(interest)
        parts["interests"] = earned / sum(weights)

    party = profile.get("travel_party")
    if party:
        # Only a signal present in the tour data or its evidence counts as party fit.
        parts["travel_party"] = 1.0 if party_evidence(text, party) else 0.0

    budget = profile.get("budget_per_person")
    price = tour.get("price")
    if budget and price is not None:
        if price <= budget:
            parts["budget"] = 1.0 - min(1.0, price / budget) * 0.4
        else:
            parts["budget"] = max(0.0, 1.0 - (price - budget) / budget)

    pace = profile.get("pace")
    if pace and pace != "balanced":
        parts["pace"] = 1.0 if pace_evidence(text, pace) else 0.0

    active = {key: value for key, value in parts.items() if key in WEIGHTS}
    divisor = sum(WEIGHTS[key] for key in active) or 1.0
    total = sum(WEIGHTS[key] * value for key, value in active.items()) / divisor
    return total, reasons


def ranked_with_reasons(tours, profile, sources=()):
    scores, texts = evidence_by_tour(sources)
    ceiling = max(scores.values()) if scores else 0.0
    ranked = []
    for tour in tours:
        tour_id = tour["tourId"]
        semantic = scores.get(tour_id, 0.0) / ceiling if ceiling else None
        total, reasons = score_tour(tour, profile, semantic, texts.get(tour_id, ""))
        ranked.append({"tour": tour, "score": total, "reasons": reasons})
    ranked.sort(key=lambda row: (-row["score"], row["tour"]["price"], row["tour"]["tourId"]))
    return ranked


def rank_tours(tours, profile, sources=()):
    return [row["tour"] for row in ranked_with_reasons(tours, profile, sources)]


def party_supported(tour, party, evidence_text=""):
    """Whether the data justifies presenting this tour as fitting ``party``."""
    return bool(party) and bool(party_evidence(tour_text(tour, evidence_text), party))


def build_itinerary(tours, profile):
    days = profile.get("days", 1)
    per_day = 2 if profile.get("pace") == "relaxed" else 3
    budget = profile.get("budget_per_person")
    total, itinerary = 0, []
    for tour in tours:
        if len(itinerary) >= days * per_day:
            break
        if budget is not None and total + tour["price"] > budget:
            continue
        total += tour["price"]
        index = len(itinerary)
        matching = [i for i in profile.get("interests", [])
                    if interest_evidence(tour_text(tour), i)]
        itinerary.append({
            "day": index // per_day + 1,
            "time": ("09:00", "14:00")[index % per_day] if per_day == 2
                    else ("09:00", "11:30", "14:00")[index % per_day],
            "activity": tour["title"], "tour_id": tour["tourId"],
            "reason": "Matches: " + ", ".join(matching) if matching else "Fits destination and remaining budget",
            "estimated_cost": tour["price"], "source": "DynamoDB Tours/" + tour["tourId"],
            "schedule_note": "Proposed slot, not verified opening hours or a reservation",
            "tour_start_date": tour["startDate"], "tour_end_date": tour["endDate"]})
    return itinerary


def reduce_day(itinerary, day, limit):
    result, count = [], 0
    for activity in deepcopy(itinerary):
        if activity["day"] == day:
            count += 1
            if count > limit:
                continue
        result.append(activity)
    return result


# --- Zero-result diagnosis -------------------------------------------------------------
# Hard constraints are never relaxed silently. These helpers only *explain* which
# constraint removed every candidate and what the nearest alternatives would cost.
HARD_KEYS = ("place", "max_price", "start_date", "status")


def blocking_constraints(catalogue, constraints):
    """Hard keys whose removal, on its own, would produce at least one candidate.

    Empty means no single key explains the empty result: the combination does.
    """
    from services.repository import filter_tours
    present = [key for key in HARD_KEYS if constraints.get(key) is not None]
    blocking = []
    for key in present:
        reduced = {k: v for k, v in constraints.items() if k != key}
        if filter_tours(catalogue, reduced):
            blocking.append(key)
    return blocking


def tradeoffs(tour, constraints):
    """The specific ways ``tour`` violates the user's hard constraints."""
    from services.normalization import normalize_place
    result = []
    place = constraints.get("place")
    if place and normalize_place(tour.get("place")) != normalize_place(place):
        result.append(("place", tour.get("place")))
    maximum = constraints.get("max_price")
    if maximum is not None and tour["price"] > maximum:
        result.append(("max_price", tour["price"] - maximum))
    start = constraints.get("start_date")
    if start is not None and tour["startDate"] < start:
        result.append(("start_date", tour["startDate"]))
    status = constraints.get("status")
    if status and fold(tour.get("status", "")) != fold(status):
        result.append(("status", tour.get("status", "")))
    return result


def closest_tours(catalogue, constraints, limit=3):
    """Nearest candidates, preferring the fewest and smallest constraint violations.

    The destination is kept whenever any tour exists there: swapping the destination is a
    bigger change than any other, and must be offered explicitly rather than assumed.
    """
    from services.repository import filter_tours
    pool = catalogue
    if constraints.get("place"):
        same_place = filter_tours(catalogue, {"place": constraints["place"]})
        pool = same_place or catalogue
    maximum = constraints.get("max_price") or 1

    def distance(tour):
        violations = tradeoffs(tour, constraints)
        overrun = next((value for key, value in violations if key == "max_price"), 0)
        return (len(violations), overrun / maximum, tour["price"], tour["tourId"])

    return sorted(pool, key=distance)[:limit]
