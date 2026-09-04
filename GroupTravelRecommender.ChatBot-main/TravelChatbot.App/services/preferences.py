"""Soft-preference vocabulary shared by parsing, ranking and the offline fixtures.

Hard constraints (destination, explicit maximum budget, explicit date/status) live in
``TravelState["constraints"]``. Everything defined here is a *soft* preference: it changes
ranking and wording, never which tours are allowed through the filter.
"""
import re
import unicodedata


def fold(text):
    """Lowercase, strip Vietnamese diacritics, collapse whitespace.

    Defined here rather than imported so this vocabulary stays free of package imports:
    both ``models.state`` and ``services.normalization`` depend on it.
    """
    text = unicodedata.normalize("NFD", str(text).lower().replace("đ", "d"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


INTERESTS = ("history", "culture", "food", "nature", "beach", "photography",
             "shopping", "adventure", "relaxation", "nightlife", "local_experience")
TRAVEL_PARTIES = ("family", "couple", "friends", "solo")
PACES = ("relaxed", "balanced", "busy")

# Folded (diacritic-free, lowercase) surface forms. Vietnamese and English share one table.
INTEREST_WORDS = {
    "history": ("history", "historical", "heritage", "lich su", "di san", "di tich", "co do"),
    "culture": ("culture", "cultural", "van hoa", "festival", "le hoi", "museum", "bao tang",
                "temple", "cung dinh"),
    "food": ("food", "cuisine", "culinary", "street food", "am thuc", "do an", "mon an",
             "an uong", "quan an", "dac san"),
    "nature": ("nature", "natural", "thien nhien", "canh quan", "mountain", "nui", "forest",
               "rung", "waterfall", "thac", "hang dong", "cave"),
    "beach": ("beach", "seaside", "bai bien", "bien ", "island", "hon dao", "vinh "),
    "photography": ("photography", "photo", "photograph", "chup anh", "song ao", "check in",
                    "check-in", "canh dep"),
    "shopping": ("shopping", "mua sam", "market", "cho dem", "souvenir", "qua luu niem"),
    "adventure": ("adventure", "trekking", "hiking", "trek", "leo nui", "mao hiem", "phieu luu",
                  "kayak", "zipline", "lan bien", "diving"),
    # "a relaxed trip" describes pace, not an activity interest, so the shared adjectives
    # stay in PACE_WORDS only; these words name relaxation as something the trip is about.
    "relaxation": ("relaxation", "chill", "spa", "resort", "nghi duong", "thu thai",
                   "an duong", "tam suoi"),
    "nightlife": ("nightlife", "night life", "bar", "pub", "club", "ve dem", "pho di bo dem"),
    "local_experience": ("local experience", "local life", "authentic", "homestay", "lang nghe",
                         "dia phuong", "ban dia", "nguoi dan", "trai nghiem dia phuong"),
}
PARTY_WORDS = {
    "family": ("family", "families", "gia dinh", "tre nho", "tre em", "con nho", "em be",
               "kids", "children", "child", "bo me", "ba me", "ong ba", "ca nha"),
    "couple": ("couple", "honeymoon", "romantic", "nguoi yeu", "ban gai", "ban trai", "cap doi",
               "vo chong", "hai dua", "lang man", "tuan trang mat"),
    "friends": ("friends", "friend", "ban be", "nhom ban", "hoi ban", "dong nghiep", "lu ban"),
    "solo": ("solo", "alone", "by myself", "mot minh", "di mot minh", "ca nhan toi"),
}
PACE_WORDS = {
    "relaxed": ("relaxed", "relaxing", "chill", "slow", "slower", "thu gian", "nhe nhang",
                "cham rai", "thong tha", "thu thai", "it diem"),
    "balanced": ("balanced", "moderate", "can bang", "vua phai", "vua du"),
    "busy": ("packed", "intensive", "jam-packed", "day dac", "kin lich", "nhieu diem",
             "di nhieu", "kham pha nhieu", "gap rut"),
}
# "prefer X over Y" / "ưu tiên X hơn Y": the right-hand side is explicitly deprioritised.
PRIORITY_SPLIT = re.compile(r"\b(?:hon|over|more than|rather than|instead of|thay vi)\b")
PRIORITY_LEAD = re.compile(r"\b(?:uu tien|prefer|prioriti[sz]e|thich|quan tam|focus on|"
                           r"care more about|muon)\b")


def _match(words, text):
    return any(word in text for word in words)


def detect_interests(text):
    """Ordered interest list. Priority phrasing puts the preferred side first."""
    value = " " + fold(text) + " "
    lead, tail = value, ""
    if PRIORITY_LEAD.search(value):
        parts = PRIORITY_SPLIT.split(value, maxsplit=1)
        if len(parts) == 2:
            lead, tail = parts
    preferred = [name for name in INTERESTS if _match(INTEREST_WORDS[name], lead)]
    demoted = [name for name in INTERESTS
               if tail and _match(INTEREST_WORDS[name], tail) and name not in preferred]
    return preferred, demoted


def detect_travel_party(text):
    value = " " + fold(text) + " "
    for name in TRAVEL_PARTIES:
        if _match(PARTY_WORDS[name], value):
            return name
    return None


def detect_pace(text):
    value = " " + fold(text) + " "
    for name in PACES:
        if _match(PACE_WORDS[name], value):
            return name
    return None


def has_soft_preference(data):
    return bool(data.get("interests") or data.get("travel_party") or data.get("pace")
                or data.get("deprioritized_interests"))


def merge_interests(existing, preferred, demoted):
    """Preferred interests move to the front; explicitly deprioritised ones are dropped."""
    merged = list(preferred)
    for name in existing or ():
        if name not in merged and name not in (demoted or ()):
            merged.append(name)
    return merged


def party_evidence(text, party):
    """Return the surface forms in ``text`` that actually support ``party``.

    Empty means the data does not support the claim, and no suitability may be stated.
    """
    if not party:
        return []
    value = " " + fold(text) + " "
    return [word.strip() for word in PARTY_WORDS[party] if word in value]


def pace_evidence(text, pace):
    if not pace:
        return []
    value = " " + fold(text) + " "
    return [word.strip() for word in PACE_WORDS[pace] if word in value]


def interest_evidence(text, interest):
    value = " " + fold(text) + " "
    return [word.strip() for word in INTEREST_WORDS.get(interest, ()) if word in value]
