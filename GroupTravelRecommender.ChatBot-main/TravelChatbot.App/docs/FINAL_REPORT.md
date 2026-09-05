# Final implementation report

P0/P1 are implemented and verified locally with mocks, actual graph/UI execution and
explicitly synthetic fixtures. Live cloud acceptance and container deployment remain
blocked as described below. This is not a claim of production deployment.

## 1. Final architecture

Streamlit owns one controller/session. Typed LangGraph routes each request to a single
domain node. DynamoDB owns business facts and registrations; Pinecone owns scored
heritage chunks ingested offline from S3. Azure OpenAI extracts structured intent and
selects evidence. Python validates quotes/citations and controls booking transitions.
See ARCHITECTURE.md for diagrams.

## 2. Files changed

Existing files updated:
- app.py, config.py, agents/controller_agent.py.
- tools/tour_tools.py, tools/tour_search.py, utilities/pdf_reader.py.
- requirements.txt, Dockerfile, .dockerignore, run_app.bat, run_app.sh, test.py, README.md.
- The pre-existing untracked .env.example was extended; .env was not modified.

New implementation:
- models/state.py.
- services/cloud.py, repository.py, rag.py, ingestion.py, planning.py, normalization.py,
  backend.py and demo.py.
- scripts/ingest.py, evaluate_rag.py and capture_ui.py.
- pytest.ini, requirements-dev.txt and tests/unit, tests/integration, tests/regression.
- eval/fixtures/heritage.json, rag_cases.json, live_cases.json and fixture-results.json.
- docs/AUDIT.md, ARCHITECTURE.md, RAG_DESIGN.md, USER_STORIES.md, MVP_FEATURES.md,
  TEST_PLAN.md, TEST_RESULTS.md, DEPLOYMENT.md, DEMO_SCRIPT.md, PRESENTATION.md,
  SCREENSHOTS.md, this report, pytest XML and five screenshots.

The existing domain models and helper agents were retained. No commit, push, merge,
history rewrite or cloud provisioning/deletion was performed.

## 3. RAG pipeline

S3 -> physical-page parsing -> normalization -> overlapping page-local chunks ->
metadata -> bounded embedding batches -> validated Pinecone upsert -> completion manifest.
Query -> embedding -> metadata filters -> active version check -> score threshold ->
bounded evidence -> verified extractive excerpts -> metadata-owned citations.
No evidence yields abstention. No PDF embedding occurs inside a user request.

## 4. LangGraph flow and state

START -> understand_query -> one domain route -> compose_answer -> END.
Routes cover search, details, heritage, groups, itinerary edits, registrations, booking,
cancellation, out-of-domain and errors. Required state fields are present, with checkpointed
messages, profile, shortlist, selection, sources, itinerary and pending action.
Memory survives Streamlit reruns; it is not durable across process restarts.

## 5. Group travel

Extract destination, people, days, budget/person, interests and pace. Filter current
tours, rank interests with optional semantic heritage evidence, allocate proposed
activities within the known tour subtotal budget, and preserve other days on a day edit.
Unknown meal/transport/ticket expenses are not invented. Proposed slots are not verified
calendar schedules. Preferences are aggregated, not individually optimized.

## 6. Booking safety

An exact target and user-supplied phone are reviewed before confirmation. Generic "yes"
does not authorize. Confirmation expires after ten minutes and is invalidated on target/
destination changes. LLM-invented phones are ignored. Only the graph injects approved
tool context. Current price/date/status is rechecked; conditional PutItem prevents duplicates.
The original schema records one phone/tour registration, not group seat reservations.

## 7. Tests and actual results

63 pytest cases passed. Python compileall and pip check passed. Streamlit AppTest and
headless browser demo were executed. Native health endpoint returned ok.
See TEST_RESULTS.md and test-results.xml for commands and evidence.

## 8. RAG evaluation

Four positive plus two negative fixture cases ran. Hit@3, Recall@5, abstention correctness,
structural citation correctness and exact-fact grounded answer rate were each 1.0.
These are synthetic local contract checks only. Live evaluation reports
BLOCKED BY ENVIRONMENT because real labeled source PDFs were not supplied.

## 9. Exact run commands

From TravelChatbot.App, using the venv created during this task:

~~~powershell
$env:DEMO_MODE="true"
.\.venv\Scripts\python -m streamlit run app.py
~~~

The local demo server was left available at http://127.0.0.1:8501 after verification.

For tests:
~~~powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts/evaluate_rag.py --fixture
~~~

For live mode after filling .env:
~~~powershell
Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue
.\.venv\Scripts\python scripts/ingest.py
.\.venv\Scripts\python scripts/evaluate_rag.py
.\.venv\Scripts\python -m streamlit run app.py
~~~

Docker after starting the engine:
~~~bash
docker build -t travel-rag .
docker run --rm --env-file .env -p 8501:8501 travel-rag
~~~

## 10. Manual setup still required

Supply Azure chat/embedding configuration, existing Pinecone index and namespace,
S3 PDFs/bucket, AWS credentials/role and correct DynamoDB tables/indexes.
Verify statuses, timestamps, model compatibility and dimensions. Populate live golden
labels from actual documents. Start Docker Engine for image validation. Public access
requires verified identity/authorization beyond the original phone-only contract.

## 11. Rubric coverage

Innovation: mixed-interest profile and editable plan.
RAG: offline ingestion, metadata, batches, scores, abstention and citations.
UI: profile/chat/cards/confirmation and five desktop/mobile images.
LLM relevance: typed extraction and source-verified answers; live relevance unmeasured.
Testing: regressions, failure paths, injection tests, SDK stubs and honest evaluation.
Deployment/demo: Dockerfile, exact setup and five-minute walkthrough; image build blocked.
No hackathon score is self-awarded. See PRESENTATION.md.

## 12. Known limitations

No public authentication, durable distributed memory, OCR, capacity transaction, live
weather/routing, per-person voting, semantic reranker or production monitoring stack.
Legacy place normalization scans the small catalog. Old generations can reduce top-k
recall; prefer fresh release namespaces. Extractive validation proves source membership,
not source truth or universal injection resistance. S3 links expire. Cloud integration
and real-corpus accuracy are not verified. Docker Engine was unavailable.

## 13. Demo script

Group request in Hue -> inspect profile and proposed itinerary -> reduce Day 1 ->
ask why Thien Mu Pagoda -> inspect source -> request first tour -> supply demo phone ->
explicitly confirm -> repeat to show duplicate prevention. Include the unsupported
pyramids query to demonstrate abstention. Full timing/script: DEMO_SCRIPT.md.

## Acceptance checklist

| Requirement | Status and evidence |
| --- | --- |
| App starts | PASS in native demo and AppTest |
| Config validation | PASS unit tests and missing-env CLI |
| Offline ingestion | Implemented, real PDF/batch tests; live BLOCKED |
| Retrieval scores | PASS retained and tested |
| Low-relevance abstention | PASS |
| Grounded RAG | PASS extractive fixtures; live BLOCKED |
| Real citations | Metadata/physical pages verified locally; real S3 links BLOCKED |
| Conversation memory | PASS reference/isolation tests |
| Group preferences | PASS |
| Itinerary | PASS proposed plan |
| Itinerary follow-up | PASS day-only edits |
| Tour filtering | PASS place/price, adapter constraints |
| Booking confirmation | PASS |
| Duplicate booking | PASS conditional-write tests and demo |
| Out-of-domain handling | PASS |
| Prompt injection test | Present and passing; live adversarial eval BLOCKED |
| API failures | PASS mocked timeout/Pinecone/LLM failures |
| pytest suite | 63 passed |
| Golden dataset | Synthetic fixture set present; real live labels BLOCKED |
| Evaluation script | Fixture results recorded; live fails explicitly as blocked |
| README | Updated to actual commands and limitations |
| Hackathon docs | Present |
| Deployment instructions | Present; image build BLOCKED by engine |
| Demo script | Present and local scenario exercised |
