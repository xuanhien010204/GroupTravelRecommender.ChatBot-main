# Presentation material

## Slide 1: Common Ground
Different interests. One shared journey.
A Vietnam group travel copilot with inspectable evidence.
Speaker note: introduce the four-person Hue scenario.

## Slide 2: Group decisions need memory
Destination, people, days, budget, interests and pace survive follow-ups.
Tour selections and day edits remain in typed LangGraph state.
Visual: screenshots/01-group.png and screenshots/02-itinerary.png.

## Slide 3: Facts have owners
DynamoDB owns price/date/status; S3/Pinecone own heritage evidence.
The LLM understands queries and selects evidence. Tools control writes.
Visual: ARCHITECTURE.md online diagram.

## Slide 4: Retrieval is a pipeline
Offline pages, batches, dimensions and completion manifests.
Online filters, scores, abstention and verified quotations/citations.
Visual: RAG_DESIGN.md and screenshots/03-sources.png.

## Slide 5: Actions require consent
Exact review, explicit confirmation, current-detail recheck, atomic duplicates.
No model-generated boolean can authorize a write.
Visual: screenshots/04-confirmation.png.

## Slide 6: Evidence
Show TEST_RESULTS.md and eval/fixture-results.json.
Fixture metrics are not live accuracy. Disclose Docker/cloud/live-corpus blockers.

## Slide 7: Next validation
Obtain PDFs and labeled queries, evaluate thresholds, verify IAM/date/status behavior,
then add identity authorization before public launch.

## Rubric coverage

| Rubric | Max | Evidence offered, not an awarded score |
| --- | ---: | --- |
| Innovation/use case | 20 | Group profile, interests, budget subtotal, editable itinerary |
| RAG pipeline | 25 | Ingestion, scores, manifests, pages, abstention and citations |
| UI | 15 | Cards, source inspection, confirmation, desktop/mobile screenshots |
| LLM relevance | 15 | Structured extraction, references, verified excerpts; live relevance unmeasured |
| Testing/robustness | 10 | pytest, SDK stubs, failure/injection/booking regressions and fixture evaluation |
| Deployment/demo | 15 | Dockerfile, setup, reproducible demo and screenshots; image deployment blocked |

No rubric points or live accuracy are self-awarded.
