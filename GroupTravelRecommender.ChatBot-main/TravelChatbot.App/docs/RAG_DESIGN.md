# RAG design

## Offline ingestion

~~~mermaid
flowchart LR
    D[DynamoDB heritageGuide keys] --> S[S3 PDF]
    S --> P[Parser with physical pages]
    P --> N[Unicode and whitespace normalization]
    N --> C[Page-local overlapping chunks]
    C --> M[Source metadata and content hash]
    M --> E[Batched Azure embeddings]
    E --> V[Pinecone upserts]
    V --> A[Publish completion manifest]
~~~

Each chunk carries chunk_id, tour_id and legacy tourId, canonical place, document_name,
source_key, physical PDF page, chunk_index, type, version and raw_text. Additional
document_id, content_hash and signature identify its generation.
Section is omitted because extraction cannot establish it reliably.

Chunk IDs hash document identity, bytes, chunk settings and embedding deployment, plus
ordinal. A manifest updates only after every batch succeeds. Retrieval accepts candidates
only from the manifest's active generation. A partial failure cannot replace the last
complete document. --reindex forces embeddings/upserts without deleting cloud data.
Upsert counters exclude manifest vectors. Document counts are tour-document associations.

PDFs over MAX_PDF_BYTES fail. Scans with no text require separate OCR. Batch cardinality
and dimensions are validated. The existing index dimension is authoritative;
EMBEDDING_DIMENSION adds an optional check. No hard-coded 1536 or index creation.

Retries are bounded for timeouts, 429 and transient 5xx; auth/input errors fail without
repeated retries. AWS uses botocore standard retries with a total-attempt cap.

## Query and grounding

~~~mermaid
flowchart LR
    U[Question and remembered context] --> Q[Constraints and semantic query]
    Q --> E[Query embedding]
    E --> R[Pinecone type/version/place/tour filters]
    R --> A[Active-generation check]
    A --> G[Keep score and relevance gate]
    G --> C[Bounded context]
    C --> L[LLM selects relevant verbatim excerpts]
    L --> V[Verify substring and source ID]
    V --> O[Answer and metadata citations]
    G -->|No evidence| X[Explicit abstention]
    V -->|No valid excerpts| X
~~~

DynamoDB supplies price, date, status and registrations. Tour constraints do not depend
on stale vector price fields. Semantic heritage matches can rank relevant tours.

RAG_TOP_K=8, RAG_MIN_SCORE=0.65 and context limit=5 are defaults, not evaluated optimums.
No reranker has been added without live evidence.

The LLM sees document text as untrusted data and selects at most three excerpts.
Code rejects unknown IDs, non-verbatim text, invalid lengths and known instruction-like
passages. Citations/pages/links come from metadata. Presigned links expire after
SOURCE_LINK_TTL. Source cards render plain text; quoted Markdown is escaped.

Accepted quotes occur in the supplied source. This does not independently prove the
source is true, every quote is relevant, or all prompt injection attacks are defeated.
These require corpus governance and adversarial evaluation.

## Evaluation

eval/rag_cases.json contains four positive and two negative synthetic golden cases.
Expected facts are exact text from eval/fixtures/heritage.json, not historical claims.
eval/live_cases.json remains empty until an operator reads real PDFs and labels sources.

Live cases need id, query, place, expected_sources (real chunk IDs), expected_facts and
should_abstain. expected_page is optional and must be a real physical page.
Fixture and live dataset modes cannot be mixed.

Metrics are calculated, never hard-coded:
- Hit@3: positive cases with a labeled source among the first three accepted matches.
- Recall@5: fraction of labeled source IDs among the first five accepted matches.
- Abstention correctness: predicted abstention equals the label.
- Citation correctness: emitted IDs belong to retrieval; answered cases have sources;
  any labeled page matches. Abstention must not emit citations.
- Grounded answer rate: positive cases return validated excerpts, valid citations and
  all expected literal facts. This is an exact-match proxy, not a human relevance score.
- Total latency: measured using a monotonic clock; fixture time is not cloud latency.

Old generations can occupy top-k before manifest filtering. Prefer a fresh namespace
for a corpus release; automatic deletion is not performed. Live calibration, deleted
document reconciliation and actual service accuracy remain blocked.
