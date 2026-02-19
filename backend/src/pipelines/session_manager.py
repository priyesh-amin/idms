import os
import json
import hashlib
import uuid
from datetime import datetime

STATE_FILE = ".agent/state/review_session.json"
REVIEW_DIR = "00-daily-ops/Inbox/review"

def calculate_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_integrity():
    """Checks if the session file exists and is consistent with the filesystem."""
    if not os.path.exists(STATE_FILE):
        return {"status": "no_session"}
    
    try:
        with open(STATE_FILE, "r") as f:
            session = json.load(f)
    except json.JSONDecodeError:
        return {"status": "corrupted", "message": "Malformed JSON in session file."}

    # Verify all files in remaining_doc_ids exist and hashes match
    for doc in session.get("remaining_docs", []):
        file_path = doc["file_path"]
        if not os.path.exists(file_path):
            return {"status": "corrupted", "message": f"File missing: {file_path}"}
        
        current_hash = calculate_hash(file_path)
        if current_hash != doc["hash"]:
            return {"status": "corrupted", "message": f"Hash drift detected for: {file_path}"}
            
    return {"status": "ok", "session": session}

def initialize_session():
    """Scans the review directory and builds a new session."""
    if not os.path.exists(REVIEW_DIR):
        return {"status": "error", "message": f"Review directory not found: {REVIEW_DIR}"}
    
    files = sorted([os.path.join(REVIEW_DIR, f) for f in os.listdir(REVIEW_DIR) if f.endswith(".pdf")])
    if not files:
        return {"status": "empty", "message": "No documents found in review folder."}
    
    remaining_docs = []
    for f in files:
        doc_id = str(uuid.uuid4())
        file_hash = calculate_hash(f)
        remaining_docs.append({
            "doc_id": doc_id,
            "hash": file_hash,
            "file_path": f,
            "orig_name": os.path.basename(f)
        })
    
    session = {
        "active": True,
        "current_doc": remaining_docs[0] if remaining_docs else None,
        "remaining_docs": remaining_docs,
        "processed_doc_ids": [],
        "started_at": datetime.now().isoformat()
    }
    
    save_session(session)
    return {"status": "success", "session": session}

def save_session(session):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(session, f, indent=2)

if __name__ == "__main__":
    import sys
    action = sys.argv[1] if len(sys.argv) > 1 else "validate"
    
    if action == "validate":
        print(json.dumps(validate_integrity()))
    elif action == "init":
        print(json.dumps(initialize_session()))
    elif action == "save":
        session_data = json.loads(sys.argv[2])
        save_session(session_data)
        print(json.dumps({"status": "success"}))
