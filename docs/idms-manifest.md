# IDMS Component Manifest (v9)

| Script Filename | Input(s) | Output (JSON) | Side Effects | Failure Mode |
|---|---|---|---|---|
| `extractor.py` | `file_path` | `{status, hash, content, telemetry...}` | None (Read-only). Real OCR via Tesseract. | Error JSON on extraction failure. |
| `analyzer.py` | `content, about_me, okrs` | `{status, context_files_read}` | None (Read-only) | Error JSON on missing context files. |
| `categorizer.py` | `content` | `{status, entity, doc_type, category, confidence...}` | **Intelligence**: Rule-based entity & signal detection. | Error JSON on empty content. |
| `renamer.py` | `type, entity, detail, ext` | `{status, filename}` | None | Error JSON on invalid chars. |
| `sheets_logger.py` | `metadata_json` | `{status, message}` | **WRITE:** Appends to Google Sheet. | Error JSON on API/Schema failure. |
| `faiss_vectorizer.py`| `doc_id, content` | `{status, message}` | **WRITE:** Updates FAISS index. Creates `.lock`. | Error JSON on lock timeout/atomic swap failure. |
| `archiver.py` | `src, dest, expected_hash`| `{status, destination, hash}`| **MOVE:** Moves file. **DELETE:** Deletes source. | Error JSON on hash mismatch. Source preserved. |
| `rebuild_index.py` | `meta_csv, drive_root` | `{status, message}` | **WRITE:** Full rebuild of FAISS index. | Error JSON on recovery failure. |
| `pipeline_runner.py` | `file_path` (optional) | `{status, results}` | Execution Layer orchestrating sequence. | Error JSON if any sub-step fails. |

**Total Scripts:** 9 (Execution Layer).
**Orchestration:** Antigravity (Agent).
