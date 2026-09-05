# Actual verification results

Date: 2026-09-05. Environment: Windows, Python 3.12, project-local .venv.
Dependencies: versions pinned in requirements.txt. Optional screenshots use Playwright
1.62.0 and an installed headless Microsoft Edge.

| Check | Observed result |
| --- | --- |
| Python compileall for app/config/agents/tools/models/services/scripts/utilities/tests | PASS |
| python -m pytest -q --junitxml=docs/test-results.xml | 63 passed in 5.21 seconds |
| python -m pip check | No broken requirements found |
| Native Streamlit demo startup | Server started at 127.0.0.1:8501 |
| GET /_stcore/health | ok |
| Streamlit AppTest | Startup, group profile, itinerary and follow-up passed |
| Headless browser demo workflow | Group, day edit, heritage follow-up, review and simulated registration passed |
| Desktop/mobile screenshots | Five PNGs captured; desktop/mobile/source/confirmation images visually inspected |
| python scripts/ingest.py | BLOCKED BY ENVIRONMENT: missing live keys/endpoint/deployments/Pinecone key/S3 bucket |
| python scripts/evaluate_rag.py | BLOCKED BY ENVIRONMENT: no human-labeled live corpus |
| docker build -t travel-rag . | BLOCKED BY ENVIRONMENT: Docker Engine pipe not available |
| RTK git diff | RTK launcher could not execute; plain git read-only checks used instead |

Machine-readable pytest evidence: [test-results.xml](test-results.xml).

## Fixture evaluation

Command:
~~~bash
python scripts/evaluate_rag.py --fixture --output eval/fixture-results.json
~~~

Dataset: four positive and two negative synthetic cases, derived from the committed
fixture source text. Actual computed output is [fixture-results.json](../eval/fixture-results.json).

| Metric | Actual fixture result |
| --- | ---: |
| Hit@3 | 1.0 (4/4 positive cases) |
| Recall@5 | 1.0 mean over 4 positive cases |
| Abstention correctness | 1.0 (6/6) |
| Structural citation correctness | 1.0 (6/6) |
| Exact-fact grounded answer rate | 1.0 (4/4 positive cases) |

These values measure local lexical retrieval and deterministic evidence selection against
synthetic labels. They are NOT Azure model quality, live Pinecone accuracy, verified
historical truth or a calibrated threshold. The evaluator's miss/error regressions also
verify metrics can be zero; results are not hard-coded.

## Failures found and fixed

The first suite run had 50 passes and 3 failures: budget parsing greedily consumed digits;
the empty budget produced no itinerary; AppTest used an incorrect relative entrypoint.
These were fixed and the suite expanded with booking/manifest/evaluator regressions.

An initial screenshot script waited for a hidden Sources tab and timed out. The script now
selects the tab first, waits for completed rendering and scrolls confirmation into view.
The successful run replaced the earlier screenshots.

## Not verified

Live Azure responses/embedding dimensions, deployed index/table schemas and status semantics,
real S3 links, actual cloud ingestion/registration, live source quality, public identity
authorization, container execution and external deployment. No cloud resource was created
or deleted. No .env value was printed or changed.
