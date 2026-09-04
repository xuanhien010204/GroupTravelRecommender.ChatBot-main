# Deployment

## Existing resources required for live mode

No infrastructure provisioning is performed.

1. Azure chat deployment supporting JSON-object responses and temperature, and an
   embedding deployment. Both use OPENAI_ENDPOINT. Azure mode uses a resource-root URL;
   compatible mode uses a supplied API base such as /openai/v1/.
2. Existing Pinecone cosine index matching the embedding output dimension. Select a
   corpus namespace; dimensions are validated before queries/upserts.
3. S3 bucket of readable text PDFs. Tours.heritageGuide stores an object key, not a
   presigned URL. Runtime retrieval never downloads these PDFs.
4. Existing DynamoDB tables/indexes described below.

## DynamoDB compatibility

Tours retains its current primary key. The app scans all pages for normalized-place
search and uses tourId-index (partition tourId) for lookup. Required fields: place,
tourId, title, startDate, endDate, price. Optional: status, category, heritageGuide.
Dates remain Unix seconds and prices VND integers. UI dates use UTC+7.

For a newly designed catalog, place partition + tourId sort supports multiple tours
per place; no schema migration is attempted here. Validate the existing schema.

UserTours requires partition tourId and sort phoneNumber, with createAt/startDate numbers.
Its phoneNumber-createAt-index has partition phoneNumber and sort createAt. Conditional
PutItem uses the full primary key for duplicate prevention.

BOOKABLE_STATUSES defaults to available,active,open. Confirm actual semantics.
Unknown/empty status and past startDate fail closed. No seat-count transaction exists.

## Credentials and access

AWS uses supplied key pairs/session token or default IAM/profile credentials.
App permissions: DynamoDB Scan/Query on Tours/index; Query/PutItem on UserTours/index;
S3 GetObject for source links. Ingestion: DynamoDB Scan, S3 GetObject, embedding API,
Pinecone fetch/upsert. Runtime Pinecone needs describe/query/fetch, not create/delete.

If the live smoke test reports `not authorized to perform: dynamodb:Scan` on `Tours`,
attach an identity policy to the exact IAM user or role used by the app. The minimum
DynamoDB policy for runtime and ingestion is:

~~~json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:Scan", "dynamodb:Query"],
      "Resource": [
        "arn:aws:dynamodb:ap-southeast-2:<ACCOUNT_ID>:table/Tours",
        "arn:aws:dynamodb:ap-southeast-2:<ACCOUNT_ID>:table/Tours/index/*",
        "arn:aws:dynamodb:ap-southeast-2:<ACCOUNT_ID>:table/UserTours",
        "arn:aws:dynamodb:ap-southeast-2:<ACCOUNT_ID>:table/UserTours/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "dynamodb:PutItem",
      "Resource": "arn:aws:dynamodb:ap-southeast-2:<ACCOUNT_ID>:table/UserTours"
    }
  ]
}
~~~

Replace `<ACCOUNT_ID>` and attach it to `asrp-be` in IAM > Users > Add permissions.
Then rerun `python scripts/smoke_test.py`. If an organization SCP or permissions
boundary denies the action, an account administrator must update that control too.

Keep real secrets in a secret manager or environment. .env and local venvs are excluded
from Docker. Links last SOURCE_LINK_TTL seconds.

Phone lookup is not authentication. Use trusted private access for the hackathon.
Public deployment requires verified identity/authorization, TLS, appropriate retention
and abuse controls; these controls are explicitly not implemented by this MVP.

## Local live launch

From TravelChatbot.App:

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Remove-Item Env:DEMO_MODE -ErrorAction SilentlyContinue
python scripts/ingest.py
python -m pytest -q
python scripts/evaluate_rag.py
python -m streamlit run app.py
~~~

Keep DEMO_MODE=false in .env. Label the live corpus first; evaluation otherwise reports
BLOCKED BY ENVIRONMENT.

## Docker

Start Docker Engine/Desktop, then:

~~~bash
docker build -t travel-rag .
docker run --rm --env-file .env -p 8501:8501 travel-rag
~~~

Without credentials:

~~~bash
docker run --rm -e DEMO_MODE=true -p 8501:8501 travel-rag
~~~

Container user appuser UID 10001; port 8501; health /_stcore/health. Session-only memory
needs no volume. Reverse proxies must support WebSockets. Multiple replicas need shared
durable checkpoints and an identity/session design; do not scale this MVP unchanged.

No external deployment was performed. Local Docker build was blocked by the missing
engine pipe. The native demo server/health check passed independently, not as evidence
of a successful image build.

## Corpus releases

Use a new namespace, ingest completely, label/evaluate, switch PINECONE_NAMESPACE and
restart. Keep the earlier namespace for rollback. No delete command is provided.
Failed document batches leave the previous complete manifest active.
