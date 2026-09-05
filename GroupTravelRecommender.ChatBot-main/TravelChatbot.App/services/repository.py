"""DynamoDB remains authoritative for price/date/status and registrations."""
import time
from functools import cached_property
from botocore.exceptions import ClientError
from models.tour import Tour
from models.user_tour import UserTour
from services.cloud import aws_session
from services.normalization import fold, normalize_place


def filter_tours(tours, constraints):
    result = []
    for tour in tours:
        if constraints.get("place") and normalize_place(tour["place"]) != normalize_place(constraints["place"]):
            continue
        if constraints.get("tour_id") and tour["tourId"] != constraints["tour_id"]:
            continue
        maximum = constraints.get("max_price")
        if maximum is not None and (tour["price"] > maximum if constraints.get("price_inclusive")
                                    else tour["price"] >= maximum):
            continue
        if constraints.get("status") and fold(tour.get("status", "")) != fold(constraints["status"]):
            continue
        if constraints.get("start_date") is not None and tour["startDate"] < constraints["start_date"]:
            continue
        result.append(tour)
    return sorted(result, key=lambda tour: (tour["price"], tour["tourId"]))


def validate_phone(phone):
    import re
    if not re.fullmatch(r"\+?\d{9,15}", phone or ""):
        raise ValueError("Enter a phone number containing 9 to 15 digits")


class TourRepository:
    def __init__(self, settings, client=None):
        self.settings, self._client = settings, client

    @cached_property
    def client(self):
        from botocore.config import Config
        return self._client or aws_session(self.settings).client("dynamodb", config=Config(
            connect_timeout=10, read_timeout=self.settings.api_timeout_seconds,
            retries={"mode": "standard", "total_max_attempts": self.settings.api_max_attempts}))

    def _pages(self, operation, **kwargs):
        while True:
            response = getattr(self.client, operation)(**kwargs)
            yield from response.get("Items", [])
            key = response.get("LastEvaluatedKey")
            if not key:
                break
            kwargs["ExclusiveStartKey"] = key

    def all_tours(self):
        return [Tour.from_dynamodb(item).to_dict()
                for item in self._pages("scan", TableName=self.settings.tours_table)]

    def search(self, constraints):
        if constraints.get("tour_id"):
            tour = self.get(constraints["tour_id"])
            return filter_tours([tour] if tour else [], constraints)
        # Legacy records use multiple spellings as partition keys; normalize after paginated scan.
        params = {"TableName": self.settings.tours_table}
        expressions, values, names = [], {}, {}
        for field, attribute, operator in (
            ("max_price", "price", "<=" if constraints.get("price_inclusive") else "<"),
            ("start_date", "startDate", ">="), ("status", "status", "=")):
            if constraints.get(field) is not None:
                names["#" + field] = attribute
                value = constraints[field]
                values[":" + field] = {"N": str(value)} if isinstance(value, int) else {"S": str(value)}
                expressions.append(f"#{field} {operator} :{field}")
        if expressions:
            params.update(FilterExpression=" AND ".join(expressions),
                          ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        tours = [Tour.from_dynamodb(item).to_dict() for item in self._pages("scan", **params)]
        return filter_tours(tours, constraints)

    def get(self, tour_id):
        response = self.client.query(TableName=self.settings.tours_table, IndexName="tourId-index",
            KeyConditionExpression="tourId = :t", ExpressionAttributeValues={":t": {"S": tour_id}}, Limit=1)
        items = response.get("Items", [])
        return Tour.from_dynamodb(items[0]).to_dict() if items else None

    def registered(self, phone):
        validate_phone(phone)
        rows = []
        for item in self._pages("query", TableName=self.settings.user_tours_table,
                IndexName="phoneNumber-createAt-index", KeyConditionExpression="phoneNumber = :p",
                ExpressionAttributeValues={":p": {"S": phone}}):
            row = UserTour.from_dynamodb(item).to_dict()
            row["tourDetails"] = self.get(row["tourId"])
            rows.append(row)
        return rows

    def register(self, tour, phone, *, confirmed=False):
        if not confirmed:
            return {"error": "confirmation_required"}
        validate_phone(phone)
        current = self.get(tour["tourId"])
        if not current:
            return {"error": "tour_not_found"}
        if any(current.get(k) != tour.get(k) for k in ("price", "startDate", "endDate", "status")):
            return {"error": "tour_changed"}
        statuses = {fold(s) for s in self.settings.bookable_statuses.split(",")}
        if fold(current.get("status", "")) not in statuses or current["startDate"] <= int(time.time()):
            return {"error": "tour_unavailable"}
        row = {"tourId": current["tourId"], "phoneNumber": phone,
               "createAt": int(time.time()), "startDate": current["startDate"]}
        try:
            self.client.put_item(TableName=self.settings.user_tours_table,
                Item={k: {"N" if isinstance(v, int) else "S": str(v)} for k, v in row.items()},
                ConditionExpression="attribute_not_exists(tourId) AND attribute_not_exists(phoneNumber)")
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return {"error": "already_registered"}
            raise
        return row
