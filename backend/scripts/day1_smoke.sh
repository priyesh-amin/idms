#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INFRA_DIR="$ROOT_DIR/infra"
SQL_FILE="$ROOT_DIR/backend/sql/001_init.sql"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:5000}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required" >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is required" >&2
  exit 1
fi

echo "[1/6] Starting infra containers..."
(
  cd "$INFRA_DIR"
  docker compose up -d
)

echo "[2/6] Waiting for Postgres health..."
for i in $(seq 1 30); do
  if (cd "$INFRA_DIR" && docker compose exec -T postgres pg_isready -U idms -d idms >/dev/null 2>&1); then
    break
  fi
  sleep 2
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Postgres did not become ready in time" >&2
    exit 1
  fi
done

echo "[3/6] Waiting for Qdrant health..."
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:6333/healthz" >/dev/null; then
    break
  fi
  sleep 2
  if [[ "$i" -eq 30 ]]; then
    echo "ERROR: Qdrant did not become ready in time" >&2
    exit 1
  fi
done

echo "[4/6] Applying schema migration..."
(
  cd "$INFRA_DIR"
  docker compose exec -T postgres psql -U idms -d idms < "$SQL_FILE" >/dev/null
)

echo "[5/6] Probing API status endpoints..."
curl -fsS "$API_BASE_URL/api/status" >/dev/null
curl -fsS "$API_BASE_URL/api/db/health" >/dev/null

echo "[6/6] Probing finance and RAG query endpoints..."
curl -fsS "$API_BASE_URL/api/query/invoices?q4Min=5000" >/dev/null
curl -fsS "$API_BASE_URL/api/query/vat-reclaimable" >/dev/null
curl -fsS "$API_BASE_URL/api/query/ar-overdue" >/dev/null
curl -fsS -X POST "$API_BASE_URL/api/rag/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"invoice", "topK": 3}' >/dev/null

echo "Smoke check passed: infra + schema + API query endpoints are reachable."
