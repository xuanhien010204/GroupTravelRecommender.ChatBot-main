"""Explicit offline simulation; never presented as live cloud or historical evidence."""
import json
import math
import re
from copy import deepcopy
from dataclasses import replace
from config import ROOT
from services.backend import Backend
from services.normalization import fold, parse_rules
from services.rag import HeritageRAG
from services.repository import filter_tours, validate_phone

STOP = {"the", "a", "an", "in", "is", "for", "of", "this", "and", "to", "are", "we",
        "what", "why", "it", "about", "hue", "synthetic", "planning", "fixture"}


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", fold(text))) - STOP


def fixture_documents():
    return json.loads((ROOT / "eval/fixtures/heritage.json").read_text(encoding="utf-8"))["documents"]


def fixture_tours():
    base = {"place": "Hue", "startDate": 4102444800, "endDate": 4102466400,
            "status": "available", "heritageGuide": "", "synthetic": True}
    return [
        dict(base, tourId="demo-01", title="Thien Mu Pagoda - history discussion", price=150000, category="history"),
        dict(base, tourId="demo-02", title="Hue food discovery", price=180000, category="food"),
        dict(base, tourId="demo-03", title="Riverside nature pause", price=200000, category="nature, relaxed"),
        dict(base, tourId="demo-04", title="Hue history reflection", price=220000, category="history"),
        dict(base, tourId="demo-05", title="Hoi An heritage discussion", price=250000, category="history", place="Hoi An"),
        # Party suitability is only ever claimed from a tour's own record, never assumed.
        dict(base, tourId="demo-06", title="Royal garden walk for families with children",
             price=190000, category="family, culture"),
        dict(base, tourId="demo-07", title="Perfume River couple sunset cruise",
             price=210000, category="couple, relaxation")]


class DemoRepository:
    def __init__(self):
        self.tours, self.bookings = fixture_tours(), {}

    def all_tours(self):
        return deepcopy(self.tours)

    def search(self, constraints):
        return deepcopy(filter_tours(self.tours, constraints))

    def get(self, tour_id):
        return next((deepcopy(t) for t in self.tours if t["tourId"] == tour_id), None)

    def registered(self, phone):
        validate_phone(phone)
        return [dict(row, tourDetails=self.get(tour_id))
                for (tour_id, number), row in self.bookings.items() if number == phone]

    def register(self, tour, phone, *, confirmed=False):
        if not confirmed:
            return {"error": "confirmation_required"}
        validate_phone(phone)
        key = (tour["tourId"], phone)
        if key in self.bookings:
            return {"error": "already_registered"}
        row = {"tourId": tour["tourId"], "phoneNumber": phone, "createAt": 0,
               "startDate": tour["startDate"], "simulation": True}
        self.bookings[key] = row
        return row


class DemoEmbeddings:
    """A bag-of-words fixture stand-in, not an Azure embedding model."""
    def embed(self, texts):
        return [tokens(text) for text in texts]


class DemoVectors:
    def query(self, vector, filters, top_k):
        matches = []
        for doc in fixture_documents():
            metadata = dict(doc, type="heritage_guide", version="1", chunk_index=0, chunk_id=doc["id"])
            if any(metadata.get(key) != value["$eq"] for key, value in filters.items()):
                continue
            terms = tokens(doc["raw_text"])
            score = len(vector & terms) / math.sqrt(max(1, len(vector) * len(terms)))
            matches.append({"id": doc["id"], "score": score, "metadata": metadata})
        return sorted(matches, key=lambda m: m["score"], reverse=True)[:top_k]


class DemoLanguage:
    def understand(self, text, state):
        return parse_rules(text, state)

    def synthesize(self, payload):
        """Deterministic fixture stand-in: restate the verified excerpts, invent nothing.

        A real model writes prose here; the fixture only proves the wiring and the
        verification gate, so it copies sentences that already passed quote checking.
        """
        excerpts = [str(text).strip() for text in payload.get("verified_excerpts", [])]
        joined = " ".join(excerpts).replace("In this synthetic planning fixture, ", "")
        if not joined:
            return {"summary": ""}
        prefix = ("Theo tài liệu di sản đã kiểm chứng: " if payload.get("language") == "vi"
                  else "Based on the verified heritage sources: ")
        return {"summary": prefix + joined}

    def json(self, system, payload):
        if "verified_excerpts" in payload:
            return self.synthesize(payload)
        query = tokens(payload["question"])
        if query & {"pyramid", "pyramids", "egypt", "egyptian", "weather", "president"}:
            return {"excerpts": []}
        ranked = sorted(payload["evidence"], key=lambda e: len(query & tokens(e["text"])), reverse=True)
        return {"excerpts": [{"source_id": e["source_id"], "quote": e["text"]}
                             for e in ranked[:2] if query & tokens(e["text"])]}


class DemoDocuments:
    def link(self, key):
        return None


def demo_backend(settings):
    # Fixture lexical scores are not calibrated on the Azure embedding distribution.
    settings = replace(settings, rag_min_score=0.05)
    language = DemoLanguage()
    rag = HeritageRAG(settings, DemoEmbeddings(), DemoVectors(), language, DemoDocuments())
    return Backend(settings, DemoRepository(), rag, language)
