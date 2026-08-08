from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class Tour:
    place: str
    tourId: str
    title: str
    startDate: int
    endDate: int
    price: int
    status: Optional[str] = ""
    category: Optional[str] = ""
    heritageGuide: Optional[str] = ""

    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> "Tour":
        """Parse a DynamoDB item (returned by boto3) into a Tour instance."""
        return cls(
            place=item["place"]["S"],
            tourId=item["tourId"]["S"],
            title=item["title"]["S"],
            startDate=int(item["startDate"]["N"]),
            endDate=int(item["endDate"]["N"]),
            price=int(item["price"]["N"]),
            status=item.get("status", {}).get("S") or "",
            category=item.get("category", {}).get("S") or "",
            heritageGuide=item.get("heritageGuide", {}).get("S") or "",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a regular Python dict (for output or serialization)."""
        return {
            "place": self.place,
            "tourId": self.tourId,
            "title": self.title,
            "startDate": self.startDate,
            "endDate": self.endDate,
            "price": self.price,
            "status": self.status,
            "category": self.category,
            "heritageGuide": self.heritageGuide,
        }

    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB-compatible attribute map."""
        item = {
            "place": {"S": self.place},
            "tourId": {"S": self.tourId},
            "title": {"S": self.title},
            "startDate": {"N": str(self.startDate)},
            "endDate": {"N": str(self.endDate)},
            "price": {"N": str(self.price)},
        }
        if self.status:
            item["status"] = {"S": self.status}
        if self.category:
            item["category"] = {"S": self.category}
        if self.heritageGuide:
            item["heritageGuide"] = {"S": self.heritageGuide}
        return item
