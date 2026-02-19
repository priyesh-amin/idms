# Day 1 Acceptance Criteria

Use this checklist after implementation to confirm the one-day delivery is working.

## A. Infra

- [ ] `infra/docker-compose.yml` starts both services:
  - [ ] Postgres (`pgvector/pgvector:pg16`)
  - [ ] Qdrant (`qdrant/qdrant`)
- [ ] Postgres health check passes (`pg_isready`)
- [ ] Qdrant health check passes (`/healthz`)

## B. Data Schema

- [ ] Migration `backend/sql/001_init.sql` applied successfully
- [ ] Required tables exist:
  - [ ] `documents`
  - [ ] `document_chunks`
  - [ ] `invoices`
  - [ ] `ar_items`
  - [ ] `audit_events`
- [ ] `vector` extension exists (pgvector)

## C. Ingestion Durability

- [ ] `pipeline_runner.py` uses repo-local pipeline scripts (no hardcoded external path)
- [ ] With `IDMS_WRITE_POSTGRES=1`, pipeline writes metadata to `documents`
- [ ] Invoice-like documents write to `invoices`
- [ ] With `IDMS_WRITE_QDRANT=1`, chunks are upserted to Qdrant collection

## D. Query Endpoints

- [ ] `GET /api/query/invoices?q4Min=5000` returns JSON response
- [ ] `GET /api/query/vat-reclaimable` returns JSON response
- [ ] `GET /api/query/ar-overdue` returns JSON response
- [ ] `POST /api/rag/search` returns ranked results (or empty rows with no error)

## E. Compatibility

- [ ] Existing `POST /api/process` still works
- [ ] Existing `POST /api/finalize` still works
- [ ] Existing audit chain (`backend/src/api/audit.js`) still initializes cleanly

## F. Quick Validation Command

Run:

```bash
cd ~/repos/idms
backend/scripts/day1_smoke.sh
```

Expected final output:

```text
Smoke check passed: infra + schema + API query endpoints are reachable.
```
