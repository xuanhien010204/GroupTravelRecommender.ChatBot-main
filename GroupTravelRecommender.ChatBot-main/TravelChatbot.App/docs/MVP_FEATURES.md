# MVP features and priority

## P0 implemented and tested locally

Typed session state; explicit transitions; current business facts; aliases and constraints;
offline ingestion; pages; batched embeddings; retries/dimension checks; scores/relevance;
extractive grounding; citations/abstention; pytest; separate fixture/live evaluation; docs.

## P1 implemented and tested locally

Group profile, interest-aware rankings, subtotal-limited proposed itinerary, day edits,
confirmation expiry and duplicate-safe booking, Streamlit profile/tour/itinerary/source
cards, desktop/mobile screenshots of the synthetic demo.

## Live acceptance blocked

Actual S3 PDFs, Azure chat/embedding requests, Pinecone data, DynamoDB transactions,
real presigned links, live golden labels and threshold tuning remain unverified.
Docker image execution is blocked by the unavailable local engine.

## P2 deferred

Reranking, Tavily/live data, LangSmith, durable multi-user memory and per-member preference
optimization need further evidence or operational scope.

## Preserved contracts and deliberate changes

Retained Streamlit, LangGraph, Azure OpenAI, Pinecone, DynamoDB, S3 and LangChain tools.
Retained Tour/UserTour fields and get_tours, get_heritage_guide, register_tour,
get_registered_tours names. Legacy helper agents remain available; the main app uses the
deterministic controller.

Deliberate changes: no import-time provisioning/query-time ingestion/unconfirmed writes;
normalized aliases; current DB prices; proper Dynamo pagination; no fictitious Pinecone
cursor; no raw service errors in chat. Old direct register_tour calls now return
confirmation_required by design.
