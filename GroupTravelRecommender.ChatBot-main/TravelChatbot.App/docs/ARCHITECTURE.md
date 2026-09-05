# Architecture

| Layer | Responsibility |
| --- | --- |
| app.py | Streamlit rendering, session controller and confirmation controls |
| agents/controller_agent.py | Explicit routing, context/references, safe transitions |
| models/state.py | Typed checkpoint data and validated query schema |
| services/repository.py | DynamoDB facts, pagination, conditional registrations |
| services/cloud.py | Lazy Azure/OpenAI, Pinecone, S3 adapters, retries/timeouts |
| services/rag.py | Relevance, evidence selection, exact quotations and citations |
| services/planning.py | Interest ranking, budget proposals, day edits |
| services/ingestion.py | Offline parsing/chunking and manifest publication |
| tools/tour_tools.py | LangChain tools; graph-owned write authorization |
| services/demo.py | Isolated synthetic dependencies for demonstrations/tests |

## Online workflow

~~~mermaid
flowchart TD
    START --> understand_query
    understand_query --> route_intent
    route_intent --> tour_search
    route_intent --> tour_details
    route_intent --> heritage_rag
    route_intent --> group_planner
    route_intent --> itinerary_update
    route_intent --> registered_tours
    route_intent --> booking
    route_intent --> out_of_domain
    route_intent --> cancel
    route_intent --> error
    tour_search --> compose_answer
    tour_details --> compose_answer
    heritage_rag --> compose_answer
    group_planner --> compose_answer
    itinerary_update --> compose_answer
    registered_tours --> compose_answer
    booking --> compose_answer
    out_of_domain --> compose_answer
    cancel --> compose_answer
    error --> compose_answer
    compose_answer --> END
~~~

No autonomous tool loop. One domain route per turn; graph recursion limit 8.
Exceptions become safe responses and clear pending write authorization. Logs contain
node/intent, counts, scores and latency, not request content, secrets or phone numbers.

State includes messages (add_messages reducer), current_intent, current_place,
group_preferences, candidate_tours, selected_tour, retrieved_sources, current_itinerary,
pending_action and booking_context. Extra fields track constraints, parsed query,
answer, errors, grounding and abstention. InMemorySaver checkpoints use session UUIDs;
Streamlit retains the controller in session_state.

Changing destination clears candidates, selected tour, itinerary and pending booking.
Indexed references preserve ordering. Explicit site names override earlier selections.
Only the current turn's verified source cards are displayed.

## Booking

~~~mermaid
flowchart LR
    R[Request exact tour] --> S[Read current facts and summarize]
    S --> P[Pending action REGISTER_TOUR]
    P --> C{Explicit confirmation and phone?}
    C -->|No| W[Wait without writing]
    C -->|Yes within 10 minutes| T[Inject exact target into tool]
    T --> V[Re-read tour and validate details]
    V --> D[Conditional DynamoDB PutItem]
    D --> O[Confirmed or already registered]
~~~

The global register_tour tool cannot write. The graph creates an authorized closure
only after exact confirmation of a complete snapshot. An LLM boolean cannot authorize it.
Changed price/date/status requires a new review. Conditional PutItem prevents duplicate
records for the tourId/phoneNumber primary key.

Phone-based identity is retained, not upgraded to authentication. The schema has no
inventory/group-seat transaction. Tour updates between the GSI read and PutItem are
not serialized against the tour record. Stronger availability needs known base-table
keys and a transactional business contract.

## References used

- [LangGraph checkpoint memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Pinecone metadata filters](https://docs.pinecone.io/guides/search/filter-by-metadata)
- [OpenAI embedding batches](https://developers.openai.com/api/reference/resources/embeddings/methods/create)

Installed AzureOpenAI/Pinecone SDK signatures were also inspected locally.
