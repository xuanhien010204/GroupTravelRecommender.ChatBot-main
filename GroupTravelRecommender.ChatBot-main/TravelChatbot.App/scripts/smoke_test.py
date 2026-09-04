"""Read-only connectivity checks for configured live services."""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ConfigurationError, Settings
from services.cloud import Documents, Embeddings, Language, VectorStore
from services.repository import TourRepository


def run_check(name, operation):
    try:
        detail = operation()
        print(f"PASS {name}: {detail}")
        return True
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
        if error_code:
            suffix += f" ({error_code})"
        print(f"FAIL {name}: {type(exc).__name__}{suffix}")
        if name == "dynamodb" and error_code in {"AccessDeniedException", "ResourceNotFoundException"}:
            message = getattr(exc, "response", {}).get("Error", {}).get("Message", "")
            message = re.sub(r"(?<!\d)\d{12}(?!\d)", "<ACCOUNT_ID>", message)
            print(f"  AWS detail: {message}")
        return False


def main():
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"FAIL config: {exc}")
        return 2

    if settings.demo_mode:
        print("FAIL config: set DEMO_MODE=false for live smoke tests")
        return 2

    # A multi-line expression inside an f-string needs Python 3.12; keep the call outside it.
    def scan_tours():
        response = TourRepository(settings).client.scan(
            TableName=settings.tours_table, Limit=1, Select="COUNT")
        return f'Tours readable; page_count={response.get("Count", 0)}'

    checks = [
        run_check("chat", lambda: "JSON response received" if Language(settings).json(
            "Return JSON with ok=true.", {"test": "connectivity"}).get("ok") is True
            else "response received"),
        run_check("embedding", lambda: f"dimension={len(Embeddings(settings).embed(['travel connectivity check'])[0])}"),
        run_check("pinecone", lambda: (
            lambda desc: f"dimension={desc.dimension}, metric={desc.metric}"
        )(VectorStore(settings).description)),
        run_check("dynamodb", scan_tours),
        run_check("s3", lambda: "bucket readable" if Documents(settings).client.head_bucket(
            Bucket=settings.heritage_guide_s3_bucket) is not None else "bucket readable"),
    ]
    print(f"RESULT {sum(checks)}/{len(checks)} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
