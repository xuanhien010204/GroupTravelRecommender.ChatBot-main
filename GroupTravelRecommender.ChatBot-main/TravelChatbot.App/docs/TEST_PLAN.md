# Test plan

## Automated layers

Unit: configuration bounds, secret repr, Vietnamese aliases, budgets, PDF attribution,
chunk IDs/manifests, scores, citations and injection rejection.

Integration: real LangGraph with isolated fixture dependencies; botocore Stubber schemas
and pagination; conditional writes; Pinecone active versions and dimensions; batch/retry
adapters; Streamlit AppTest.

Regression covers all sixteen requested scenarios: place, price, heritage, follow-up,
pronouns, Vietnamese normalization, negative RAG, group plan, itinerary edits, unconfirmed
booking, confirmed booking, duplicates, out of domain, Pinecone failure, LLM failure,
prompt injection inside a document. Extra tests cover isolation, phone completion,
destination changes, direct tool authority, invented phones, expiry, invalid IDs,
named sites and changed prices.

Tests forbid external socket.create_connection; adapters use mocks or SDK Stubber.
No cloud-service success is inferred.

## Commands

Run from TravelChatbot.App with the project venv activated:

~~~bash
python -m compileall -q app.py config.py agents tools models services scripts utilities tests
python -m pytest -q --junitxml=docs/test-results.xml
python scripts/evaluate_rag.py --fixture --output eval/fixture-results.json
python scripts/evaluate_rag.py
~~~

With a DEMO_MODE=true server on 127.0.0.1:8501:

~~~bash
python -m pip install -r requirements-dev.txt
python scripts/capture_ui.py --channel msedge
~~~

Capture uses a fresh headless context, verifies the offline banner, walks group planning,
day edit, heritage follow-up, review/confirmation and simulated registration, then saves
desktop/mobile PNGs. It does not use a real signed-in browser profile.

## Live acceptance

Supply cloud configuration and real PDFs. Ingest into an existing test namespace.
Read sources and label eval/live_cases.json. Include wrong-place, high-overlap/no-answer,
Vietnamese alias and adversarial-document cases. Use an authorized isolated test phone
and tour for live registration. Inspect the actual database record and verify date/status/
IAM behavior. No live success is claimed until these checks execute.
