import time
import boto3
from botocore.exceptions import ClientError
from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, HERITAGE_GUIDE_S3_BUCKET
from models.tour import Tour
from models.user_tour import UserTour
from models.tour_tool_args import GetRegisteredToursArgs, GetToursArgs, GetHeritageGuideArgs, RegisterTourArgs
from typing import List, Dict, Any, Optional
from langchain.tools import tool
from tools.tour_search import embed_tours, search_tours, embed_pdf_chunks, search_tour_heritage, heritage_chunk_exists
from utilities.pdf_reader import chunk_text, extract_text_from_pdf_bytes
from utilities.s3_utils import download_s3_object, generate_presigned_url

@tool(args_schema=GetRegisteredToursArgs)
def get_registered_tours(phoneNumber: str) -> List[Dict[str, Any]]:
    """Retrieve all registered tours for a given phone number with additional tour details."""
    dynamodb = boto3.client(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    try:
        response = dynamodb.query(
            TableName="UserTours",
            IndexName="phoneNumber-createAt-index",
            KeyConditionExpression="phoneNumber = :p",
            ExpressionAttributeValues={":p": {"S": phoneNumber}},
        )

        items = response.get("Items", [])
        registered_tours = []
        
        for item in items:
            user_tour = UserTour.from_dynamodb(item)
            user_tour_dict = user_tour.to_dict()
            
            # Fetch the full tour details from the Tours table
            try:
                tour_response = dynamodb.query(
                    TableName="Tours",
                    IndexName="tourId-index",
                    KeyConditionExpression="tourId = :t",
                    ExpressionAttributeValues={":t": {"S": user_tour.tourId}},
                    Limit=1
                )
                tour_items = tour_response.get("Items", [])
                if tour_items:
                    tour = Tour.from_dynamodb(tour_items[0])
                    tour_dict = tour.to_dict()
                    
                    # Generate presigned URL for heritageGuide if it exists
                    if tour_dict.get("heritageGuide"):
                        pre_signed_url = generate_presigned_url(
                            s3_client=s3_client,
                            bucket=HERITAGE_GUIDE_S3_BUCKET,
                            key=tour_dict["heritageGuide"]
                        )
                        if pre_signed_url:
                            tour_dict["heritageGuide"] = pre_signed_url

                    user_tour_dict["tourDetails"] = tour_dict
            except ClientError as e:
                user_tour_dict["tourDetails"] = {"error": e.response["Error"]["Message"]}
            
            registered_tours.append(user_tour_dict)
        
        return registered_tours

    except ClientError as e:
        return [{"error": e.response["Error"]["Message"]}]

@tool(args_schema=GetToursArgs)
def get_tours(
    place: Optional[str] = None,
    search_query: Optional[str] = None,
    type: Optional[str] = None,
    pagination_token: Optional[str] = None,
    page_size: int = 10,
) -> Dict[str, Any]:
    """Retrieve existing tours with pagination support.

    Supports three modes:
    1. No parameters: returns all tours
    2. place parameter: queries tours for that specific location
    3. search_query parameter: performs semantic search based on the query

    Returns paginated results with a next page token.
    """
    # If there's a search query, go directly to semantic search
    if search_query:
        return search_tours(
            query=search_query,
            type="tour_info",
            place=place,  # Pass the place parameter for filtering
            pagination_token=pagination_token,
            page_size=page_size
        )

    # For non-search queries, use DynamoDB pagination
    dynamodb = boto3.client(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    try:
        # Build the base query parameters
        query_params = {
            "TableName": "Tours",
            "Limit": page_size
        }

        # Add pagination token if provided
        if pagination_token:
            query_params["ExclusiveStartKey"] = {"S": pagination_token}

        # Add place filter if provided
        if place:
            query_params.update({
                "KeyConditionExpression": "place = :p",
                "ExpressionAttributeValues": {":p": {"S": place}}
            })
            response = dynamodb.query(**query_params)
        else:
            response = dynamodb.scan(**query_params)

        # Convert items to tour dictionaries
        items = response.get("Items", [])
        tours = [Tour.from_dynamodb(item).to_dict() for item in items]
        
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Generate presigned URLs for heritageGuide if present
        for tour in tours:
            if tour.get("heritageGuide"):
                presigned_url = generate_presigned_url(
                    s3_client=s3_client,
                    bucket=HERITAGE_GUIDE_S3_BUCKET,
                    key=tour["heritageGuide"]
                )
                if presigned_url:
                    tour["heritageGuide"] = presigned_url

        return {
            "results": tours,
            "next_token": None
        }

    except ClientError as e:
        return {
            "results": [],
            "next_token": None,
            "error": e.response["Error"]["Message"]
        }


@tool(args_schema=GetHeritageGuideArgs, response_format="content_and_artifact")
def get_heritage_guide(
    place: str,
    search_query: Optional[str] = None,
    pagination_token: Optional[str] = None,
    page_size: int = 10,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Retrieve heritage guide information for a specific place.

    Returns detailed cultural and historical information from available heritage guides.
    """
    metadata = { "RAG_usage": True }
    result = {
        "results": [],
        "next_token": None
    }

    try:
        search_query_final = search_query
        if search_query_final is None:
            search_query_final = f"top {page_size} sites to visit in {place}"
        # 1) Use `search_tours` to find tour metadata for this place (prefer vector index)
        tour_search_results = search_tours(query=search_query_final, place=place, type="tour_info", page_size=1)
        tours_metadata = tour_search_results.get("results", [])

        # If no tours found via vector search return not found heritage guides
        if not tours_metadata:
            return result, metadata

        # 2) For each tour metadata, check whether the first chunk exists in the heritage index.
        #    If any tour has existing chunk(s), we'll query the heritage index normally.
        existingTour = None
        for meta in tours_metadata:
            if meta.get("place").casefold() == place.casefold():
                existingTour = meta
                break

        if existingTour is None:
            return result, metadata

        tourId = existingTour["tourId"]
        # 3) If we have existing chunks in Pinecone, query heritage index directly
        if existingTour is not None and heritage_chunk_exists(chunk_id = f"{tourId}_heritageGuide_0"):
            place_query = f"{search_query_final} in {place}" if search_query_final else place
            search_results = search_tour_heritage(
                query=place_query,
                place=place,
                pagination_token=pagination_token,
                page_size=page_size,
            )

            # Filter (defensive) and return
            results = [r for r in search_results.get("results", []) if r.get("place") == place]
            next_token = search_results.get("next_token") if len(results) >= page_size else None
            return {"results": results, "next_token": next_token}, metadata

        heritageGuide = existingTour.get("heritageGuide")
        print("Not existing embeded data, fetching heritage guide S3 key:", heritageGuide)
        if not heritageGuide:
            return result, metadata
        
        try:
            s3_client = boto3.client("s3",
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION,
            )
            pdf = download_s3_object(HERITAGE_GUIDE_S3_BUCKET, heritageGuide, s3_client)
            if pdf.get("body"):
                text = extract_text_from_pdf_bytes(pdf["body"])
                if text:
                    chunks = chunk_text(text, chunk_size=2000, overlap=200)
                    if chunks:
                        try:
                            embed_pdf_chunks(chunks, existingTour)
                        except Exception as e:
                            print(f"Error embedding chunks for tour {tourId}: {str(e)}")
        except Exception as e:
            print(f"Error fetching/embedding heritage guide for tour {tourId}: {str(e)}")

        # After embedding, query the heritage index for this place
        place_query = f"{search_query_final} in {place}" if search_query_final else place
        search_results = search_tour_heritage(
            query=place_query,
            place=place,
            pagination_token=pagination_token,
            page_size=page_size,
        )

        results = [r for r in search_results.get("results", []) if r.get("place") == place]
        next_token = search_results.get("next_token") if len(results) >= page_size else None
        return {"results": results, "next_token": next_token}, metadata

    except Exception as e:
        print(f"Error in get_heritage_guide: {str(e)}" )
        return {
            "results": [],
            "next_token": None,
            "error": str(e)
        }, metadata
    
    
@tool(args_schema=RegisterTourArgs)
def register_tour(tourId: str, phoneNumber: str) -> Dict[str, Any]:
    """Register a tour for a phone number. Requires tourId and phoneNumber."""
    
    dynamodb = boto3.client(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )

    try:
        # 1) Find the tour by tourId using the tourId-index
        resp = dynamodb.query(
            TableName="Tours",
            IndexName="tourId-index",
            KeyConditionExpression="tourId = :t",
            ExpressionAttributeValues={":t": {"S": tourId}},
            Limit=1
        )
        items = resp.get("Items", [])
        if not items:
            raise ValueError("tour not found")

        tour_item = items[0]
        tour = Tour.from_dynamodb(tour_item)
        start_date = int(tour.startDate)

        # 2) Check if the tour is already registered for this phoneNumber
        resp_check = dynamodb.query(
            TableName="UserTours",
            KeyConditionExpression="tourId = :t AND phoneNumber = :p",
            ExpressionAttributeValues={
                ":t": {"S": tourId},
                ":p": {"S": phoneNumber}
            },
            Limit=1
        )
        if resp_check.get("Items"):
            raise ValueError("tour is registered")

        # 3) Register the tour
        created_at = int(time.time())
        dynamodb.put_item(
            TableName="UserTours",
            Item={
                "tourId": {"S": tourId},
                "phoneNumber": {"S": phoneNumber},
                "createAt": {"N": str(created_at)},
                "startDate": {"N": str(start_date)}
            }
        )

        return {
            "tourId": tourId,
            "phoneNumber": phoneNumber,
            "createAt": created_at,
            "startDate": start_date
        }

    except ClientError as e:
        return {"error": e.response["Error"]["Message"]}

