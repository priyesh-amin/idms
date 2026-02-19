# IDMS_DIRECTIVE_V6

## 1. INTENT
Govern autonomous ingestion and conversational audit of files from `00-daily-ops/Inbox` to `06-long-term-memory/` using the DOE framework and Persistent Review Lifecycle (v12).

## 2. GOVERNANCE
- **Orchestrator:** Antigravity (Sole Authority). Manages the logic, decision-making, and conversational review session.
- **Architecture:** Directive -> Orchestration -> Execution (Stateless).
- **Execution Layer:** Stateless scripts (e.g., `pipeline_runner.py`) that perform discrete actions and return JSON results.
- **Thresholds:**
    - **Auto-Process:** Confidence >= 0.85.
    - **Review:** Confidence < 0.85 (Gated for safety).
- **Truth Source (Metadata):** Google Sheets (Audit + Audit Log).
- **Truth Source (Semantic):** Local FAISS (Vector Index).
- **Truth Source (Identity):** Deterministic SHA-256 (Binary source of truth).
- **Truth Source (Session):** `.agent/state/review_session.json` (Persistent Review State).

## 3. EXECUTION PIPELINE
1. **[Extractor]** -> Real OCR Fallback (Tesseract) + SHA-256 generation.
2. **[Categorizer]** -> Rule-based signal detection + Weighted Header Analysis.
3. **[Decision]** -> 
    - Approval -> Side Effects.
    - Review -> Move to `00-daily-ops/Inbox/review/` + Initialize Session.
4. **[Renamer]** -> Standardize to `YYYY-MM-DD_<DocType>_<Entity>_<Detail>.pdf`.
5. **[Review Lifecycle]** -> Conversational Audit via agent-rendered Review Cards.
6. **[Finalization]** -> Move, Log to Sheets, and Update FAISS only after **explicit binary hash verification**.

## 4. REVIEW SESSION MANAGEMENT (v12)
- **Conversational Lock:** The agent focuses on one document at a time based on a deterministic queue.
- **Integrity Guard:** Every approval/edit requires a valid 64-character SHA-256 hash match.
- **Recovery:** Session Corruption Guard ensures `.agent/state/review_session.json` is consistent with the filesytem; rebuild on drift.
- **Persistence:** Supports `Pause`, `Resume`, and `Skip` without context loss.

## 5. RECOVERY & FAILURE HANDLING
- **No Silent Failures:** All errors logged to Sheets `error_log`.
- **Integrity Rebuild:** `rebuild_index.py` re-reads original PDFs to ensure 100% embedding parity.
- **Rollback:** Move operations are verified twice (Pre/Post) and automatically rolled back on hash mismatch.

## 6. SECRETS MANAGEMENT
- **Credentials:** `credentials.json` path provided via `IDMS_SHEETS_CRED_PATH`.
- **Access:** Restricted Service Account scope.
