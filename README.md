# Apollo-Zoho Enricher

A **real-time enrichment microservice** that connects Zoho CRM to Apollo.io.  
When you click a custom button in Zoho, it sends your company name (and optionally its domain) to this service. Behind the scenes:

1. **FastAPI** accepts the request and immediately returns a `202 Accepted` with a `task_id`.
2. **Celery** (backed by Redis) picks up the enrichment job.
3. **Apollo.io API** calls resolve the domain, fetch full organization data, then search & enrich key people.
4. **MySQL** stores core records in `companies` & `people` tables and full JSON blobs in `organization_details` & `person_details`.
5. _(Future)_: A periodic Celery task will push the enriched data back up to Zoho via the Zoho v2 REST API.

---

## 📦 Features

- **Non-blocking API** – Zoho UI never waits on your enrichment call.
- **Idempotent upserts** – avoids duplicate companies or people.
- **Rate-limit & retry** – automatic backoff on Apollo’s 429s.
- **Modular code** – clear separation of API, tasks, DB, and third-party clients.
- **Docker-Compose** “batteries included” for dev: FastAPI, Celery worker & beat, Redis, MySQL.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** (or Docker & Docker-Compose)
- **Redis 7.x** (if running locally)
- **MySQL 8.x** (if running locally)
- An **Apollo.io API key** (set `APOLLO_API_KEY`)
- _(Optional)_ Zoho OAuth credentials (for push-back phase)

### 1. Clone & Install

```bash
git clone <your-repo-url> apollo-zoho-enricher
cd apollo-zoho-enricher

# install Python deps via Poetry
poetry install
# or, if you just need deps: `poetry install --no-root`
```
