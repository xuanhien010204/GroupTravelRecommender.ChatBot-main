from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class GetRegisteredToursArgs(BaseModel):
    """Arguments for get_registered_tours tool."""
    model_config = ConfigDict(extra="allow")
    
    phoneNumber: str = Field(
        description="The customer's phone number. Used to look up all tours registered under this number."
    )


class GetToursArgs(BaseModel):
    """Arguments for get_tours tool."""
    model_config = ConfigDict(extra="allow")
    
    place: Optional[str] = Field(
        default=None,
        description=(
            "The name of the place in Vietnam to filter tours by. "
            "If omitted, returns all available tours."
        ),
    )
    search_query: Optional[str] = Field(
        default=None,
        description=(
            "Natural language query for semantic search. Examples: "
            "'tours in Hoi An', 'tours under 600000 VND', 'tourId abc123-xyz'"
        ),
    )
    type: Optional[str] = Field(
        default=None,
        description="Filter by document type."
    )
    pagination_token: Optional[str] = Field(
        default=None,
        description="Token for getting the next page of results. Omit for first page."
    )
    page_size: int = Field(
        default=10,
        description="Number of results to return per page. Default is 10."
    )


class GetHeritageGuideArgs(BaseModel):
    """Arguments for get_heritage_guide tool."""
    model_config = ConfigDict(extra="allow")
    
    place: str = Field(
        description="The name of the place in Vietnam to get heritage guide information for."
    )
    search_query: Optional[str] = Field(
        default=None,
        description=(
            "Optional natural language query to search within heritage guides. "
            "Examples: 'Hue\'s tourist information', 'Hue\'s heritage sites', 'Places to visit in Hue'"
        ),
    )
    pagination_token: Optional[str] = Field(
        default=None,
        description="Token for getting the next page of results."
    )
    page_size: int = Field(
        default=10,
        description="Number of results to return per page. Default is 10."
    )


class RegisterTourArgs(BaseModel):
    """Arguments for register_tour tool."""
    model_config = ConfigDict(extra="allow")
    
    tourId: str = Field(
        description="The tour unique identifier."
    )
    phoneNumber: str = Field(
        description="The customer's phone number used for registration."
    )
