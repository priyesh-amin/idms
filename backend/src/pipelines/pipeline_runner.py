import os
import sys
import json
import uuid
import argparse
import subprocess
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "..", "..", ".."))
BASE_IDMS = os.environ.get("BASE_IDMS", REPO_ROOT)
INBOX = os.environ.get("IDMS_INBOX_PATH", os.path.join(BASE_IDMS, "00-daily-ops", "Inbox"))
REVIEW_DIR = os.environ.get("IDMS_REVIEW_PATH", os.path.join(BASE_IDMS, "00-daily-ops", "Inbox", "review"))

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2 (v1.0.0)"

WRITE_POSTGRES = os.environ.get("IDMS_WRITE_POSTGRES", "0").strip().lower() in {"1", "true", "yes", "on"}
WRITE_QDRANT = os.environ.get("IDMS_WRITE_QDRANT", "0").strip().lower() in {"1", "true", "yes", "on"}


def run_step(script_name, *args):
    """Runs a pipeline step script and returns parsed JSON output."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        return {"status": "error", "message": f"Script not found: {script_name}"}

    cmd = [sys.executable, script_path] + list(args)
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
        start = result.find("{")
        end = result.rfind("}")
        if start != -1 and end != -1:
            return json.loads(result[start : end + 1])
        return json.loads(result)
    except subprocess.CalledProcessError as exc:
        output = exc.output.decode("utf-8")
        start = output.find("{")
        end = output.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(output[start : end + 1])
            except Exception:
                pass
        return {"status": "error", "message": output}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def process_file(file_path, dry_run=False, verbose=False, overrides=None):
    filename = os.path.basename(file_path)

    extraction = run_step("extractor.py", file_path)
    if extraction.get("status") == "error":
        return {
            "status": "aborted",
            "message": extraction.get("message", "Extraction failed"),
            "hash": extraction.get("hash", "None"),
            "confidence": 0,
            "routing": "review",
            "telemetry": {
                "file_size_bytes": extraction.get("file_size_bytes", 0),
                "pages_processed": extraction.get("pages_processed", 0),
                "extraction_method": extraction.get("extraction_method", "failed"),
                "ocr_used": extraction.get("ocr_used", False),
                "ocr_dpi": extraction.get("ocr_dpi", 0),
                "extracted_text_length": 0,
                "confidence": 0,
                "embedding_model": EMBEDDING_MODEL,
            },
        }

    content = extraction["content"]
    file_hash = extraction["hash"]
    file_size = extraction["file_size_bytes"]
    pages_processed = extraction["pages_processed"]
    extraction_method = extraction["extraction_method"]
    ocr_used = extraction["ocr_used"]
    ocr_dpi = extraction["ocr_dpi"]
    ocr_engine_version = extraction["ocr_engine_version"]
    extracted_text_length = extraction["extracted_text_length"]

    cat_res = run_step("categorizer.py", content)
    if cat_res.get("status") == "error":
        return cat_res

    category = cat_res["category"]
    doc_type = cat_res["doc_type"]
    entity = cat_res["entity"]
    confidence = cat_res["confidence"]
    entity_confidence = cat_res["entity_confidence"]

    if overrides:
        category = overrides.get("category", category)
        doc_type = overrides.get("doc_type", doc_type)
        entity = overrides.get("entity", entity)
        confidence = 1.0

    routing = "auto"
    if entity_confidence < 0.85 or confidence < 0.85:
        routing = "review"

    date_val = overrides.get("date") if overrides else None
    rename_args = [doc_type, entity, "Import", "pdf"]
    if date_val:
        rename_args.append(date_val)

    rename_res = run_step("renamer.py", *rename_args)
    if rename_res.get("status") == "error":
        return rename_res

    new_filename = rename_res["filename"]

    is_hash_valid = len(file_hash) == 64 and all(c in "0123456789abcdef" for c in file_hash.lower())

    doc_id = overrides.get("doc_id", str(uuid.uuid4())) if overrides else str(uuid.uuid4())
    metadata = {
        "doc_id": doc_id,
        "timestamp": datetime.now().isoformat(),
        "orig_name": filename,
        "new_name": new_filename,
        "category": category,
        "doc_type": doc_type,
        "entity": entity,
        "confidence": confidence,
        "entity_confidence": entity_confidence,
        "path": f"06-long-term-memory/{category}/{new_filename}",
        "status": "preview" if dry_run else ("processed" if routing == "auto" else "review"),
        "hash": file_hash,
        "pages_processed": pages_processed,
        "extraction_method": extraction_method,
        "ocr_used": ocr_used,
        "ocr_dpi": ocr_dpi,
        "ocr_engine_version": ocr_engine_version,
        "extracted_text_length": extracted_text_length,
        "embedding_model": EMBEDDING_MODEL,
        "signals_detected": cat_res.get("signals_detected", []),
        "hash_valid": is_hash_valid,
    }

    if dry_run:
        side_effects = [
            {"step": "Sheets Logger", "action": f"Append Row (Simulated - {routing})"},
            {"step": "FAISS Vectorizer", "action": "Atomic Index Update (Simulated)"},
            {"step": "Archiver", "action": "Move File (Simulated)", "destination": metadata["path"]},
        ]
        if WRITE_POSTGRES:
            side_effects.append({"step": "Postgres Logger", "action": "Upsert metadata + invoice rows (Simulated)"})
        if WRITE_QDRANT:
            side_effects.append({"step": "Qdrant Vectorizer", "action": "Upsert chunk vectors (Simulated)"})

        return {
            "status": "dry-run-preview",
            "routing_decision": routing,
            "file_size_bytes": file_size,
            "pages_processed": pages_processed,
            "extraction_method": extraction_method,
            "ocr_used": ocr_used,
            "ocr_dpi": ocr_dpi,
            "extracted_text_length": extracted_text_length,
            "confidence": confidence,
            "entity_confidence": entity_confidence,
            "embedding_model": EMBEDDING_MODEL,
            "proposed_metadata": metadata,
            "proposed_side_effects": side_effects,
        }

    is_in_review = os.path.abspath(file_path).startswith(os.path.abspath(REVIEW_DIR))
    if routing == "review" and not is_in_review:
        dest_dir = REVIEW_DIR
        run_step("archiver.py", file_path, dest_dir, file_hash)
        return {
            "status": "review",
            "message": "Low confidence or entity mismatch, routed to review.",
            "doc_id": doc_id,
            "hash": file_hash,
        }

    # Existing integrations retained
    log_res = run_step("sheets_logger.py", json.dumps(metadata))
    if log_res.get("status") == "error":
        return log_res

    vector_res = run_step("faiss_vectorizer.py", doc_id, content)
    if vector_res.get("status") == "error":
        return vector_res

    # New durable persistence path
    if WRITE_POSTGRES:
        pg_res = run_step("postgres_logger.py", json.dumps(metadata), content)
        if pg_res.get("status") == "error":
            return {
                "status": "error",
                "message": f"Postgres persistence failed: {pg_res.get('message')}",
                "doc_id": doc_id,
            }

    qdrant_warning = None
    if WRITE_QDRANT:
        qdrant_res = run_step("qdrant_vectorizer.py", doc_id, content, json.dumps(metadata))
        if qdrant_res.get("status") == "error":
            qdrant_warning = qdrant_res.get("message")

    dest_dir = f"06-long-term-memory/{category}"
    archive_res = run_step("archiver.py", file_path, dest_dir, file_hash, new_filename)
    archive_res["metadata"] = metadata
    if qdrant_warning:
        archive_res["warnings"] = [f"Qdrant indexing warning: {qdrant_warning}"]
    return archive_res


def main():
    parser = argparse.ArgumentParser(description="IDMS Pipeline Runner (Execution Layer)")
    parser.add_argument("--file", help="Process a single file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without side effects")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging")
    parser.add_argument("--overrides", help="JSON string of metadata overrides for review")
    args = parser.parse_args()

    overrides = None
    if args.overrides:
        try:
            overrides = json.loads(args.overrides)
        except Exception:
            print(json.dumps({"status": "error", "message": "Invalid overrides JSON."}))
            sys.exit(1)

    if args.file:
        result = process_file(args.file, dry_run=args.dry_run, verbose=args.verbose, overrides=overrides)
        print(json.dumps(result, indent=2 if args.verbose else None))
        return

    if not os.path.exists(INBOX):
        print(json.dumps({"status": "error", "message": f"Inbox not found: {INBOX}"}))
        sys.exit(1)

    files = [os.path.join(INBOX, f) for f in os.listdir(INBOX) if f.endswith(".pdf")]
    if not files:
        print(json.dumps({"status": "success", "message": "No files to process", "inbox": INBOX}))
        sys.exit(0)

    results = [process_file(f, dry_run=args.dry_run, verbose=args.verbose) for f in files]
    print(json.dumps(results, indent=2 if args.verbose else None))


if __name__ == "__main__":
    main()
