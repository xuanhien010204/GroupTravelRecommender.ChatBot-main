# User stories and use cases

| User story | Acceptance evidence |
| --- | --- |
| Find tours by place/budget without invented prices. | Place, price, alias and semantic-filter regressions; DynamoDB tests |
| Ask about the second option and then "it". | Checkpointed shortlist, selection and pronoun tests |
| Retain the group's destination, people, days, budget, interests and pace. | Profile assertions and Streamlit scenario test |
| Simplify Day 1 without changing Day 2. | Day-specific regression and browser scenario |
| Inspect evidence behind heritage advice. | Quote/source tests, physical PDF pages, source cards |
| Hear an explicit admission when evidence is absent. | Negative RAG cases for pyramids in Quy Nhon and Hue |
| Review before registering; avoid duplicate records. | Confirmation, expiry, wrong-target and conditional-write tests |
| Ingest PDFs before the demo and understand failures. | Offline counters, manifests, batch/retry tests |

Primary use case: a four-person mixed-interest group planning two days in Hue.
Secondary cases: individual search, cultural questions and registered-tour lookup.
Out of scope: payment, inventory, delivery, live weather, verified transport routing,
general-purpose assistance and independent web research.
