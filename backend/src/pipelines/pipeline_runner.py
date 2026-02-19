import os
import sys
import json
import uuid
import argparse
from datetime import datetime
import subprocess

# Paths to components
INBOX = "00-daily-ops/Inbox"
REVIEW_DIR = "00-daily-ops/Inbox/review"
SCRIPTS_DIR = "00-daily-ops/scripts/idms"

# Secret Management (V5)
CRED_PATH = os.environ.get("IDMS_SHEETS_CRED_PATH")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2 (v1.0.0)"

def run_step(script_name, *args):
    """Execution Layer: Runs a pipeline step script and returns JSON."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        return {"status": "error", "message": f"Script not found: {script_name}"}
        
    cmd = [sys.executable, script_path] + list(args)
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        # Robust JSON extraction: Find the first '{' and last '}'
        start = result.find('{')
        end = result.rfind('}')
        if start != -1 and end != -1:
            json_str = result[start:end+1]
            return json.loads(json_str)
        return json.loads(result)
    except subprocess.CalledProcessError as e:
        # Try to extract JSON from error output too
        output = e.output.decode('utf-8')
        start = output.find('{')
        end = output.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(output[start:end+1])
            except: pass
        return {"status": "error", "message": output}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def process_file(file_path, dry_run=False, verbose=False, overrides=None):
    """
    Pipeline Execution Logic. Supports dry-run and live modes.
    Overrides can be provided for conversational review edits.
    """
    filename = os.path.basename(file_path)
    
    # 1. Extractor (Real execution)
    extraction = run_step("extractor.py", file_path)
    
    if extraction["status"] == "error":
        return {
            "status": "aborted",
            "message": extraction["message"],
            "hash": extraction.get("hash", "None"),
            "confidence": 0,
            "routing": "/review",
            "telemetry": {
                "file_size_bytes": extraction.get("file_size_bytes", 0),
                "pages_processed": extraction.get("pages_processed", 0),
                "extraction_method": extraction.get("extraction_method", "failed"),
                "ocr_used": extraction.get("ocr_used", False),
                "ocr_dpi": extraction.get("ocr_dpi", 0),
                "extracted_text_length": 0,
                "confidence": 0,
                "embedding_model": EMBEDDING_MODEL
            }
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

    # 2. Categorization & Entity Extraction (Real logic)
    cat_res = run_step("categorizer.py", content)
    if cat_res["status"] == "error": return cat_res

    category = cat_res["category"]
    doc_type = cat_res["doc_type"]
    entity = cat_res["entity"]
    confidence = cat_res["confidence"]
    entity_confidence = cat_res["entity_confidence"]

    # Apply Overrides if provided (from Natural Language Review)
    if overrides:
        category = overrides.get("category", category)
        doc_type = overrides.get("doc_type", doc_type)
        entity = overrides.get("entity", entity)
        # Recalculate confidence if edited? (v12 requirement)
        # For now, we assume the user's manual edit is high confidence
        confidence = 1.0 if overrides else confidence 

    # 3. Decision Logic & Routing
    routing = "auto"
    if entity_confidence < 0.85 or confidence < 0.85:
        routing = "review"

    # 4. Renamer
    date_val = overrides.get("date") if overrides else None
    args = [doc_type, entity, "Import", "pdf"]
    if date_val:
        args.append(date_val)
    rename_res = run_step("renamer.py", *args)
    
    if rename_res["status"] == "error":
        return rename_res
        
    new_filename = rename_res["filename"]

    # 4.5 Integrity Validation (SHA-256)
    is_hash_valid = len(file_hash) == 64 and all(c in "0123456789abcdef" for c in file_hash.lower())

    # 5. Metadata Assembly
    doc_id = overrides.get("doc_id", str(uuid.uuid4())) if overrides else str(uuid.uuid4())
    metadata = {
        "doc_id": doc_id,
        "timestamp": datetime.now().isoformat(),
        "orig_name": filename,
        "new_name": new_filename,
        "category": category,
        "entity": entity,
        "confidence": confidence, 
        "path": f"06-long-term-memory/{category}/{new_filename}",
        "status": "preview" if dry_run else ("processed" if routing == "auto" else "review"),
        "hash": file_hash,
        "pages_processed": pages_processed,
        "extraction_method": extraction_method,
        "ocr_used": ocr_used,
        "ocr_dpi": ocr_dpi,
        "extracted_text_length": extracted_text_length,
        "embedding_model": EMBEDDING_MODEL,
        "ocr_engine_version": ocr_engine_version,
        "signals_detected": cat_res.get("signals_detected", []),
        "hash_valid": is_hash_valid
    }

    if dry_run:
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
            "proposed_side_effects": [
                {"step": "Sheets Logger", "action": f"Append Row (Simulated - {routing})"},
                {"step": "FAISS Vectorizer", "action": "Atomic Index Update (Simulated)"},
                {"step": "Archiver", "action": "Move File (Simulated)", "destination": metadata["path"]}
            ]
        }
    else:
        # Live Execution (Gated by Routing)
        # If the file is ALREADY in the review folder, we don't route it to review again
        is_in_review = "review" in file_path
        
        if routing == "review" and not is_in_review:
            dest_dir = REVIEW_DIR
            run_step("archiver.py", file_path, dest_dir, file_hash)
            return {"status": "review", "message": "Low confidence or entity mismatch, routed to review.", "doc_id": doc_id, "hash": file_hash}

        # Live Finalization
        # 1. Sheets Logger
        log_res = run_step("sheets_logger.py", json.dumps(metadata))
        if log_res["status"] == "error": return log_res

        # 2. Vectorizer
        vector_res = run_step("faiss_vectorizer.py", doc_id, content)
        if vector_res["status"] == "error": return vector_res

        # 3. Archiver
        dest_dir = f"06-long-term-memory/{category}"
        archive_res = run_step("archiver.py", file_path, dest_dir, file_hash, new_filename)
        
        # Ensure we return the metadata for the agent to log
        archive_res["metadata"] = metadata
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
        except:
            print(json.dumps({"status": "error", "message": "Invalid overrides JSON."}))
            sys.exit(1)

    if args.file:
        result = process_file(args.file, dry_run=args.dry_run, verbose=args.verbose, overrides=overrides)
        print(json.dumps(result, indent=2 if args.verbose else None))
    else:
        if not os.path.exists(INBOX):
            sys.exit(1)
        files = [os.path.join(INBOX, f) for f in os.listdir(INBOX) if f.endswith(".pdf")]
        if not files:
            sys.exit(0)
        
        results = [process_file(f, dry_run=args.dry_run, verbose=args.verbose) for f in files]
        print(json.dumps(results, indent=2 if args.verbose else None))

if __name__ == "__main__":
    main()
