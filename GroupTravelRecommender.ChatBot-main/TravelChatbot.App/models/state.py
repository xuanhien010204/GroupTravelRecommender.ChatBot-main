from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, field_validator
from services.preferences import INTERESTS

Interest = Literal["history", "culture", "food", "nature", "beach", "photography",
                   "shopping", "adventure", "relaxation", "nightlife", "local_experience"]


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["tour_search", "tour_details", "heritage_rag", "group_planner",
                    "itinerary_update", "registered_tours", "booking", "refine_preferences",
                    "out_of_domain"] = "out_of_domain"
    place: str | None = None
    max_price: int | None = Field(default=None, ge=0)
    price_inclusive: bool = False
    start_date: int | None = Field(default=None, ge=0)
    status: str | None = None
    semantic_query: str = ""
    tour_id: str | None = None
    selected_index: int | None = Field(default=None, ge=1, le=100)
    phone_number: str | None = None
    people: int | None = Field(default=None, ge=1, le=100)
    days: int | None = Field(default=None, ge=1, le=30)
    budget_per_person: int | None = Field(default=None, ge=0)
    interests: list[Interest] | None = None
    deprioritized_interests: list[Interest] | None = None
    travel_party: Literal["family", "couple", "friends", "solo"] | None = None
    pace: Literal["relaxed", "balanced", "busy"] | None = None
    itinerary_day: int | None = Field(default=None, ge=1, le=30)
    activity_limit: int | None = Field(default=None, ge=1, le=10)

    @field_validator("interests", "deprioritized_interests", mode="before")
    @classmethod
    def _known_interests(cls, value):
        """Drop anything outside the vocabulary instead of failing the whole extraction."""
        if not isinstance(value, list):
            return value
        seen, kept = set(), []
        for item in value:
            name = str(item).strip().lower().replace(" ", "_")
            if name in INTERESTS and name not in seen:
                seen.add(name)
                kept.append(name)
        return kept or None


class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    current_intent: str
    current_place: str | None
    group_preferences: dict
    candidate_tours: list[dict]
    selected_tour: dict | None
    retrieved_sources: list[dict]
    current_itinerary: list[dict]
    pending_action: str | None
    booking_context: dict
    constraints: dict
    query: dict
    answer: str
    error: str | None
    grounded: bool
    abstained: bool
    registered_tours: list[dict]
    confirmation_received: bool
    language: str
