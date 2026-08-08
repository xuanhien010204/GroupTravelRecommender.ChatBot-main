from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

def fetch_s3_object(bucket: str, key: str, s3_client, max_inline_bytes: int = 5 * 1024 * 1024) -> Dict[str, Any]:
    """Fetch object metadata and content (if small) from S3.

    Returns a dict containing:
    - presigned_url: a short-lived presigned URL for the object
    - content_type, content_length
    - error on failure
    """
    result: Dict[str, Any] = {}
    try:
        # Get head to inspect size and content-type
        head = s3_client.head_object(Bucket=bucket, Key=key)
        content_length = int(head.get("ContentLength", 0))
        content_type = head.get("ContentType")

        # Generate presigned URL to download by chunks
        presigned = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600,
        )

        result.update({
            "presigned_url": presigned,
            "content_type": content_type,
            "content_length": content_length,
        })
        return result

    except ClientError as e:
        return {"error": e.response.get("Error", {}).get("Message", str(e))}
    except Exception as e:
        return {"error": str(e)}


def download_s3_object(bucket: str, key: str, s3_client) -> Dict[str, Any]:
    """Download the full S3 object body (returns bytes in 'body' key).

    Returns dict with either 'body' (bytes) or 'error'.
    """
    try:
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        return {"body": body, "content_length": int(resp.get("ContentLength", len(body))), "content_type": resp.get("ContentType")}
    except ClientError as e:
        return {"error": e.response.get("Error", {}).get("Message", str(e))}
    except Exception as e:
        return {"error": str(e)}


def generate_presigned_url(bucket: str, key: str, s3_client) -> Optional[str]:

    try:
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key
            },
            ExpiresIn=86400  # 1 day in seconds
        )
        return presigned_url
    except ClientError as e:
        print(f"Error generating presigned URL for {key}: {e.response['Error']['Message']}")
        return None