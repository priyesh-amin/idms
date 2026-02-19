# IDMS One-Day Execution Framework

Baseline repo: `main` @ commit `6d9cd3c` (2026-02-19)

## 1. Day Objective
Deliver a production-ready **RAG + Accounts Automation v1** in one working day by extending the current repo (not rewriting it).

End-of-day user-visible outcomes:
1. Query: "Q4 invoices > 5k"
2. Query: "VAT reclaimable total"
3. Query: "Overdue AR invoices"
4. RAG search endpoint returning top matching docs/chunks

## 2. Reality Check From Baseline
Current strengths (keep):
1. Existing ingestion flow: extractor -> categorizer -> renamer -> archiver.
2. Existing API shell in `backend/src/api/server.js`.
3. Existing governance/audit chain in `backend/src/api/audit.js`.

Current blockers (must fix first):
1. `backend/requirements.txt` is missing.
2. `backend/src/pipelines/extractor.py` has Windows-only Tesseract/Poppler paths.
3. `backend/src/pipelines/pipeline_runner.py` uses hardcoded external script paths (`00-daily-ops/...`).
4. Sheets + FAISS components are placeholders, not durable 50M-ready storage.

## 3. Scope For This One-Day Delivery
In scope:
1. Add Dockerized Postgres + pgvector + Qdrant.
2. Add durable metadata schema for document + invoice query patterns.
3. Add ingestion writes to Postgres (and optional Qdrant write path).
4. Add query API endpoints for the 3 finance use cases.
5. Keep existing scripts operational as fallback.

Out of scope (day 1):
1. Full frontend redesign.
2. Full re-embedding/backfill of historical corpus.
3. Multi-tenant auth and full RBAC.

## 4. File-Level Work Plan
## 4.1 Infrastructure
1. Add `infra/docker-compose.yml`:
   - `postgres` with `pgvector/pgvector:pg16`
   - `qdrant` with persistent volume
2. Add `backend/.env.example` with DB/Qdrant connection settings.

## 4.2 Schema + Migrations
1. Add `backend/sql/001_init.sql` with tables:
   - `documents`
   - `document_chunks`
   - `invoices`
   - `ar_items`
   - `audit_events`
2. Add indexes for date ranges, amount filters, due-date filters, and vector columns.

## 4.3 Pipeline Integration
1. Add `backend/src/pipelines/postgres_logger.py`.
2. Add `backend/src/pipelines/qdrant_vectorizer.py`.
3. Update `backend/src/pipelines/pipeline_runner.py`:
   - keep existing flow intact
   - add feature-flagged writes to Postgres/Qdrant
4. Update `backend/src/pipelines/extractor.py` for Linux-compatible OCR path detection.

## 4.4 API Query Layer
1. Add `backend/src/api/db.js` (connection pool).
2. Add endpoints in `backend/src/api/server.js`:
   - `GET /api/query/invoices?q4Min=5000`
   - `GET /api/query/vat-reclaimable`
   - `GET /api/query/ar-overdue`
   - `POST /api/rag/search`
3. Keep existing `/api/process` and `/api/finalize` unchanged for compatibility.

## 4.5 Validation + Demo
1. Add `backend/scripts/day1_smoke.sh` to run:
   - container health checks
   - schema apply
   - one sample ingestion
   - all query endpoints
2. Add `docs/DAY1_ACCEPTANCE.md` with expected outputs.

## 5. One-Day Timeline (Aggressive)
Hour 0-1: Environment + repo wiring
1. Bring up Docker services.
2. Add env files and connection checks.

Hour 1-3: Data model
1. Implement SQL schema + indexes.
2. Run migration and confirm tables.

Hour 3-5: Ingestion path
1. Add Postgres logger and integrate into pipeline runner.
2. Persist extracted metadata for finance query use.

Hour 5-7: Query layer
1. Implement 3 finance query endpoints.
2. Implement lightweight RAG search endpoint.

Hour 7-8: Validation
1. Run smoke tests.
2. Verify expected JSON outputs.

Hour 8-9: Hardening and handoff
1. Add failure handling + logs.
2. Final demo script and runbook.

## 6. Definition of Done (End of Day)
All must be true:
1. `docker compose` for Postgres/Qdrant is up and healthy.
2. At least one ingested sample row exists in `documents` and `invoices`.
3. All 3 finance query endpoints return non-error JSON.
4. RAG search endpoint returns ranked results.
5. Existing process/finalize API flow still runs.

## 7. Command Checklist
Run from repo root:

```bash
cd ~/repos/idms

# infra
cd infra && docker compose up -d && cd ..

# backend deps (once requirements is created)
cd backend
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# migrate and run
# (migration command to be added in implementation)
node src/api/server.js
```

## 8. Execution Rule For Codex/Veda
1. Use this repo as the only source of truth for day-1 implementation.
2. Keep each change small and testable.
3. Commit by workstream:
   - `infra`
   - `schema`
   - `ingestion`
   - `query`
   - `validation`
4. No giant all-in-one commit.

## 9. Risk Controls
1. If Postgres write fails, keep existing Sheets/FAISS path alive.
2. If Qdrant integration slips, ship with Postgres + pgvector first.
3. If OCR environment is unstable, gate OCR behind fallback and continue with text PDFs.

This framework is designed to ship a usable v1 in one day while preserving your current scripts and minimizing regression risk.
