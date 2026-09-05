"""Offline S3 PDF ingestion; run explicitly, never from a chat request."""
import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ConfigurationError, Settings
from services.cloud import Documents, Embeddings, VectorStore
from services.ingestion import ingest
from services.repository import TourRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reindex", action="store_true", help="Re-embed documents; does not delete old vectors")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if settings.demo_mode:
            print("BLOCKED BY ENVIRONMENT: ingestion needs live credentials, not DEMO_MODE")
            return 2
        report = ingest(TourRepository(settings).all_tours(), Documents(settings),
                        Embeddings(settings), VectorStore(settings), settings, reindex=args.reindex)
        print(json.dumps(report, indent=2))
        return 1 if report["failed"] else 0
    except ConfigurationError as exc:
        print("BLOCKED BY ENVIRONMENT: " + str(exc))
        return 2
    except Exception as exc:
        print("BLOCKED BY ENVIRONMENT: ingestion could not access a configured service (" + type(exc).__name__ + ")")
        return 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
