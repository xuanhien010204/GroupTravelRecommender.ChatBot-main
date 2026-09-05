# Read-only audit

Baseline: git status contained only the previously created .env.example. No secrets were read.
The repository is Python/Streamlit, not ASRP .NET. AGENTS.md, BACKEND_AI_CONTEXT.md and
BUSINESS.md are absent. All app, agent, tool, model, utility, config, launcher, dependency,
Docker and existing test files were inspected.

## Confirmed
- Streamlit reconstructs graph input/controller on reruns; UI history is not graph memory.
- Uncontrolled tool/LLM loop; no typed application state or confirmation transition.
- Importing tour_search creates paid indexes and assumes dimension 1536.
- User requests download/parse/embed PDFs. Chunks lose page attribution.
- Embeddings called individually; retrieval discards scores and has no quality gate.
- Unsupported Pinecone pagination_token; Dynamo pagination drops LastEvaluatedKey.
- Prices can come from stale vector metadata. No Vietnamese normalization.
- Booking check-then-put has a race; no explicit confirmation.
- Raw exceptions reach chat. test.py prints live responses without assertions.
- Unpinned dependencies; Docker includes an unused Chroma directory.

## Assumptions corrected / unknown
- Code uses an OpenAI-compatible URL despite docs calling it Azure. Support explicit modes.
- No source PDF corpus or labeled live golden dataset is present.
- Cloud table keys/statuses and embedding dimensions cannot be verified from screenshots.
- Two vector indexes are not necessary: DynamoDB supplies business facts, Pinecone heritage.
- Existing screenshots show the old app, not verified new behavior.

## Plan and scope
P0: settings, lazy service adapters, typed checkpointed graph, offline page-aware batched
ingestion, scored retrieval, extractive grounding, citations, pytest, honest evaluation.
P1: group profile, matching, editable proposed itinerary, confirmation, atomic duplicates, UI.
P2: defer reranking, live web and tracing platforms until real-corpus evaluation.

Change config.py, app.py, controller_agent.py, tour_tools.py, tour_search.py, tool schemas,
PDF utility, requirements, Docker, launchers, .env.example, test.py. Add services/, scripts/,
tests/, eval/, docs/. Preserve domain models and useful tool names.
Never edit .env, provision indexes, delete resources, commit, push or merge.
