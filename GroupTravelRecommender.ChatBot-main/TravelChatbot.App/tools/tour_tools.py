"""LangChain tools; write authorization is injected by the graph, never an LLM argument."""
from langchain_core.tools import tool
from services.backend import default_backend
from services.repository import validate_phone


def build_tools(backend, approved_booking=None):
    @tool
    def get_tours(place: str | None = None, search_query: str | None = None,
                  max_price: int | None = None, page_size: int = 10,
                  pagination_token: str | None = None, type: str | None = None) -> dict:
        """Read authoritative tours; optional place/price constraints and offset pagination."""
        from services.normalization import parse_rules
        constraints = parse_rules(search_query or "").model_dump(exclude_none=True)
        if place:
            constraints["place"] = place
        if max_price is not None:
            constraints["max_price"] = max_price
        page_size = max(1, min(page_size, 100))
        offset = int(pagination_token or 0)
        if offset < 0:
            raise ValueError("Invalid pagination token")
        tours = backend.repository.search(constraints)
        end = offset + page_size
        return {"results": tours[offset:end], "next_token": str(end) if end < len(tours) else None}

    @tool
    def get_heritage_guide(place: str, search_query: str | None = None,
                           page_size: int = 8, pagination_token: str | None = None) -> dict:
        """Retrieve already ingested heritage evidence, retaining IDs, scores and metadata."""
        if pagination_token:
            raise ValueError("Vector search has no cursor; refine the query instead")
        matches = backend.rag.retrieve(search_query or f"heritage in {place}", place,
                                        top_k=max(1, min(page_size, 100)))
        return {"results": matches, "next_token": None}

    @tool
    def get_registered_tours(phoneNumber: str) -> list[dict]:
        """Read registrations and current tour details for a provided phone number."""
        return backend.repository.registered(phoneNumber)

    @tool
    def register_tour(tourId: str, phoneNumber: str) -> dict:
        """Register only the exact target authorized by a prior graph confirmation."""
        approval = approved_booking or {}
        tour = approval.get("tour", {})
        if tour.get("tourId") != tourId or approval.get("phone") != phoneNumber:
            return {"error": "confirmation_required"}
        validate_phone(phoneNumber)
        return backend.repository.register(tour, phoneNumber, confirmed=True)

    return {t.name: t for t in (get_tours, get_heritage_guide, get_registered_tours, register_tour)}


@tool
def get_tours(place: str | None = None, search_query: str | None = None,
              pagination_token: str | None = None, page_size: int = 10,
              max_price: int | None = None, type: str | None = None) -> dict:
    """Read tours by place and price, with pagination."""
    return build_tools(default_backend())["get_tours"].invoke(locals())


@tool
def get_heritage_guide(place: str, search_query: str | None = None,
                       pagination_token: str | None = None, page_size: int = 8) -> dict:
    """Retrieve heritage evidence from the existing index."""
    return build_tools(default_backend())["get_heritage_guide"].invoke(locals())


@tool
def get_registered_tours(phoneNumber: str) -> list[dict]:
    """Read registered tours."""
    return build_tools(default_backend())["get_registered_tours"].invoke(locals())


@tool
def register_tour(tourId: str, phoneNumber: str) -> dict:
    """Request registration. A graph-confirmed target is required before a write."""
    return {"error": "confirmation_required"}
