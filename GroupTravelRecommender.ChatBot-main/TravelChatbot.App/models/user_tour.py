from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class UserTour:
    tourId: str
    phoneNumber: str
    createAt: int
    startDate: int

    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> "UserTour":
        return cls(
            tourId=item["tourId"]["S"],
            phoneNumber=item["phoneNumber"]["S"],
            createAt=int(item["createAt"]["N"]),
            startDate=int(item["startDate"]["N"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to normal Python dict for model output."""
        return {
            "tourId": self.tourId,
            "phoneNumber": self.phoneNumber,
            "createAt": self.createAt,
            "startDate": self.startDate,
        }