# Common Ground: AI Group Travel Copilot

A domain-specific Vietnam travel assistant built on the existing Streamlit, LangGraph,
Azure OpenAI, Pinecone, DynamoDB, S3 and LangChain tool stack.

Tours and registrations come from DynamoDB. Heritage answers quote verified passages
from an offline-ingested corpus. Group profiles and follow-up references live in a
typed LangGraph checkpoint.

## Quick start: no cloud credentials

Python 3.12 was used for verification. From this directory:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DEMO_MODE="true"
python -m streamlit run app.py
~~~

For bash, activate with source .venv/bin/activate and use export DEMO_MODE=true.
Open http://localhost:8501. The yellow banner identifies **synthetic demo data**.
Demo retrieval uses local lexical vectors and a deterministic language stand-in; it is
not an Azure/Pinecone accuracy measurement. Demo bookings affect session memory only.

## Live setup and environment

Fill the existing local .env using [.env.example](.env.example) as a reference.
Do not overwrite existing secrets. .env is ignored by Git and Docker.

| Variables | Meaning |
| --- | --- |
| DEMO_MODE | false for cloud; true for isolated fixtures |
| OPENAI_API_MODE | azure for an Azure resource-root URL; compatible for an OpenAI-compatible base URL |
| OPENAI_ENDPOINT, OPENAI_API_VERSION | Resource root and supported API version; compatible mode uses the supplied base URL |
| OPENAI_API_KEY, OPENAI_DEPLOYMENT_NAME | Chat deployment key and deployment name |
| OPENAI_TEXT_EMBEDED_API_KEY, OPENAI_TEXT_EMBEDED_DEPLOYMENT_NAME | Embedding key and deployment; keep original spelling |
| PINECONE_API_KEY, PINECONE_HERITAGE_INDEX, PINECONE_NAMESPACE | Existing cosine index and corpus namespace |
| AWS_REGION, HERITAGE_GUIDE_S3_BUCKET | Region and existing PDF bucket |
| AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN | Optional explicit AWS credentials; otherwise IAM/profile credential chain |
| TOURS_TABLE, USER_TOURS_TABLE | Existing tables; defaults Tours and UserTours |
| BOOKABLE_STATUSES | Values matching real database semantics; unknown statuses fail closed |
| RAG_CHUNK_SIZE, RAG_CHUNK_OVERLAP | Character-based page-local chunking, defaults 1800/200 |
| RAG_TOP_K, RAG_CONTEXT_CHUNKS, RAG_MIN_SCORE | Candidates 8, context 5, provisional cosine threshold 0.65 |
| EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSION | Batch 32; dimension 0 discovers output and checks the existing index |
| LLM_TEMPERATURE | 0; chat deployment must support temperature and JSON responses |
| API_TIMEOUT_SECONDS, API_MAX_ATTEMPTS | Timeout 30 seconds, at most 3 attempts per supported operation |
| MAX_PDF_BYTES, SOURCE_LINK_TTL | PDF byte cap and presigned-link lifetime |

PINECONE_ENVIRONMENT is no longer required: no index is created by the application.
The former tours vector index is not queried; current prices/dates/status come from
DynamoDB. Existing useful tool names and DynamoDB record fields are retained.
The old compatible endpoint is supported by setting OPENAI_API_MODE=compatible.

See [DEPLOYMENT](docs/DEPLOYMENT.md) for table/index expectations and IAM scope.

~~~powershell
Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue
python scripts/ingest.py
python -m pytest -q
python scripts/evaluate_rag.py
python -m streamlit run app.py
~~~

The live evaluator needs human-labeled sources in eval/live_cases.json; otherwise it
reports BLOCKED BY ENVIRONMENT. It never silently substitutes fixtures.

## Features and architecture

- Typed conversation state, place normalization and indexed/pronoun follow-ups.
- Destination, price, date, status and tour-ID constraints applied to business data.
- Group preferences, interest-aware rankings and budget-limited proposed itineraries.
- Day-specific itinerary edits without rebuilding other days.
- Offline PDFs with real physical pages, batched embeddings and completion manifests.
- Retrieval retains IDs, scores and metadata; insufficient evidence can abstain.
- Extractive grounding verifies quotations and source IDs in code.
- Exact booking confirmation, expiry, current-detail checks and atomic duplicates.
- Profile, chat, tour, itinerary, source and confirmation cards.

~~~mermaid
flowchart LR
    U[User] --> UI[Streamlit]
    UI --> G[Typed LangGraph and session checkpoint]
    G --> D[DynamoDB tour facts]
    G --> R[Scored heritage retrieval]
    R --> P[Pinecone]
    G --> B[Confirmed booking tool]
    B --> D
    R --> L[Azure OpenAI evidence selection]
    L --> V[Quote and source validation]
    V --> UI
~~~

[Architecture](docs/ARCHITECTURE.md) | [RAG design](docs/RAG_DESIGN.md) |
[User stories](docs/USER_STORIES.md) | [MVP scope](docs/MVP_FEATURES.md)

## Ingestion and evaluation

~~~bash
python scripts/ingest.py
python scripts/ingest.py --reindex
python scripts/evaluate_rag.py --fixture --output eval/fixture-results.json
python scripts/evaluate_rag.py --cases eval/live_cases.json
~~~

Ingestion reads S3 keys referenced by Tours.heritageGuide, retains pages, batches
embeddings and publishes a manifest after all chunks succeed. Reports include scanned,
processed, chunks, embeddings, upserts, skipped and failed counts. It does not run in chat,
create indexes or delete resources. Reindexing does not perform destructive cleanup.

The committed golden fixtures contain authored synthetic documents and expected excerpts.
They validate pipeline contracts. Actual historical accuracy and the live score threshold
remain unmeasured until real PDFs are labeled. Metrics include Hit@3, Recall@5, abstention,
structural citation correctness and exact-fact grounded answer rate.
See [test plan](docs/TEST_PLAN.md) and [actual results](docs/TEST_RESULTS.md).

## Tests and Docker

~~~bash
python -m compileall -q app.py config.py agents tools models services scripts utilities tests
python -m pytest -q
docker build -t travel-rag .
docker run --rm --env-file .env -p 8501:8501 travel-rag
~~~

For a credential-free container:
~~~bash
docker run --rm -e DEMO_MODE=true -p 8501:8501 travel-rag
~~~

Docker runs as a non-root user and checks /_stcore/health.
The local build was blocked because Docker Engine was unavailable; no successful
container deployment is claimed.

## Demo and material

[Demo script](docs/DEMO_SCRIPT.md) | [Presentation](docs/PRESENTATION.md) |
[UI screenshots](docs/SCREENSHOTS.md) | [Final report](docs/FINAL_REPORT.md)

Start with:
> We are 4 people visiting Hue for 2 days. Budget is about 800000 VND/person.
> Two people like history, one likes food, and we want a relaxed schedule.

Then simplify Day 1, ask why Thien Mu Pagoda fits, and request a booking.
No write occurs until the complete target and phone have been explicitly confirmed.

## Limitations

- Verified local hackathon MVP; public production deployment is not verified.
- Phone knowledge is not authentication. Keep live lookup/registration behind trusted
  access; add verified identity and authorization before public exposure.
- In-memory checkpoints survive reruns, not process restarts/new browser sessions.
- Legacy alias support scans the small catalog. A larger dataset needs a canonical-place index.
- Proposal times are not opening hours or guaranteed tour schedules. No transport, weather,
  unverified ticket fees, seat counts or capacity guarantees are invented.
- Group preferences aggregate interests; no per-member voting/utility optimizer.
- Extractive answers favor traceability over synthesis. Injection defenses are tested,
  not proof against every adversarial document.
- No OCR; section labels are omitted rather than guessed.
- Old/incomplete generations are excluded via manifests but can reduce top-k recall.
  Use a fresh namespace per release; cleanup requires separate approval.
- Independent live labels and actual cloud-service results remain unavailable.
