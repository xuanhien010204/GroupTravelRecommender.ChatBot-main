from copy import deepcopy
from services.normalization import fold


def rank_tours(tours, profile, sources=()):
    interests = profile.get("interests", [])
    evidence = {}
    for source in sources:
        tour_id = source["metadata"].get("tour_id")
        evidence[tour_id] = max(evidence.get(tour_id, 0), source["score"])
    def score(tour):
        text = fold(tour.get("title", "") + " " + tour.get("category", ""))
        return sum(fold(interest) in text for interest in interests), evidence.get(tour["tourId"], 0)
    return sorted(tours, key=lambda tour: (-score(tour)[0], -score(tour)[1], tour["price"], tour["tourId"]))


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
                    if fold(i) in fold(tour.get("title", "") + " " + tour.get("category", ""))]
        itinerary.append({
            "day": index // per_day + 1,
            "time": ("09:00", "14:00") [index % per_day] if per_day == 2
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
