"""Evaluate fixtures or a separately labeled live corpus without inventing metrics."""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ROOT, Settings, ConfigurationError
from services.backend import create_backend


def evaluate(backend, cases):
    rows = []
    for case in cases:
        started = time.perf_counter()
        matches = backend.rag.retrieve(case["query"], case.get("place"), top_k=max(5, backend.settings.rag_top_k))
        answer = backend.rag.answer(case["query"], matches)
        expected = set(case.get("expected_sources", []))
        hit = bool(expected & {m["id"] for m in matches[:3]}) if expected else None
        recall = len(expected & {m["id"] for m in matches[:5]}) / len(expected) if expected else None
        citation_ok = all(source["id"] in {m["id"] for m in matches} for source in answer["sources"])
        if case.get("expected_page") is not None and not case["should_abstain"]:
            citation_ok = citation_ok and any(s["metadata"].get("page") == case["expected_page"]
                                               and s["id"] in expected for s in answer["sources"])
        if not answer["abstained"]:
            citation_ok = citation_ok and bool(answer["sources"])
        else:
            citation_ok = citation_ok and not answer["sources"]
        text = answer["answer"].replace("\\", "")
        grounded = (not answer["abstained"] and answer["grounded"] and citation_ok
                    and all(fact in text for fact in case.get("expected_facts", [])))
        rows.append({"id": case["id"], "hit_at_3": hit, "recall_at_5": recall,
                     "abstention_correct": answer["abstained"] == case["should_abstain"],
                     "citation_correct": citation_ok,
                     "grounded_answer": grounded if not case["should_abstain"] else None,
                     "total_latency_ms": round((time.perf_counter() - started) * 1000, 2)})
    def mean(key):
        values = [row[key] for row in rows if row[key] is not None]
        return sum(values) / len(values) if values else None
    return {"cases": rows, "metrics": {key: mean(key) for key in
            ("hit_at_3", "recall_at_5", "abstention_correct", "citation_correct", "grounded_answer")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true", help="Run labeled synthetic fixtures without external APIs")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    path = args.cases or ROOT / ("eval/rag_cases.json" if args.fixture else "eval/live_cases.json")
    try:
        dataset = json.loads(path.read_text(encoding="utf-8"))
        expected_mode = "fixture" if args.fixture else "live"
        if dataset.get("mode") != expected_mode:
            raise ValueError("Dataset mode does not match evaluation mode")
        if not dataset["cases"]:
            print("BLOCKED BY ENVIRONMENT: a human-labeled live corpus is required")
            return 2
        settings = Settings(demo_mode=True) if args.fixture else Settings.from_env()
        if not args.fixture and settings.demo_mode:
            print("BLOCKED BY ENVIRONMENT: disable DEMO_MODE for live evaluation")
            return 2
        report = {"mode": expected_mode, "provenance": dataset["provenance"],
                  **evaluate(create_backend(settings), dataset["cases"])}
        result = json.dumps(report, indent=2)
        print(result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result + "\n", encoding="utf-8")
        return 0
    except ConfigurationError as exc:
        print("BLOCKED BY ENVIRONMENT: " + str(exc))
        return 2
    except Exception as exc:
        print("Evaluation failed: " + type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
