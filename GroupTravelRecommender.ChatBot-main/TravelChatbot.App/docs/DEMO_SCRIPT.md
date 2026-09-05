# Five-minute demo

## Preparation

Start DEMO_MODE=true. State:
"These are synthetic planning fixtures. The cloud adapters exist, but this run is not
evidence of Azure/Pinecone accuracy, real prices or real bookings."

Open http://localhost:8501 and click New trip.

## 0:00 - Group profile

Say: "Groups disagree about interests and pace. We retain constraints and expose the
evidence behind recommendations."

Enter:
> We are 4 people visiting Hue for 2 days. Budget is about 800000 VND/person.
> Two people like history, one likes food, and we want a relaxed schedule.

Show people=4, days=2, budget=800000, history/food and relaxed in Trip Profile.
Show shortlist and itinerary subtotal. Explain excluded meals/transport.

## 1:15 - Memory and editing

Enter:
> Day 1 is too busy. Keep only two places.

Show retained profile and unchanged other days. Relaxed mode may already have two items:
describe this as an idempotent edit. For a visible three-to-two reduction, start with
"balanced schedule".

Optional:
> How much is the second one?
> What is special about it?

Show reference resolution.

## 2:00 - Grounding

Enter:
> Why did you choose Thien Mu Pagoda?

Open Sources. Show actual fixture text and similarity score. The fixture has no PDF
page, so none is invented. A live ingested PDF would show its real page and S3 link.

Enter:
> Are there Egyptian pyramids in Quy Nhon?

Show explicit abstention. This describes missing KB evidence, not a definitive
encyclopedic statement about the world.

## 3:00 - Controlled action

Return to Hue if the previous question changed destination:
> Find tours in Hue.
> Book the first tour.

Show review and disabled confirmation until the phone is supplied:
> 0900000000

Read title, ID, price, dates and masked phone. No registration exists yet.
Click Confirm booking; show DEMO simulation success.
Repeat the same request/confirmation and show already registered.

## 4:15 - Engineering and limits

Show architecture, pytest results and fixture-results.json. Distinguish contract tests
from blocked live evaluation. Explain offline ingestion and conditional duplicates.
Mention identity authorization is required before public deployment.

## Fallback

Use the offline demo when cloud access is unavailable. If no browser is available, use
captured screenshots/test results and label them as synthetic local evidence.
Never present a cloud failure as a successful response.
