import os
import sys
import json
import hashlib
import shutil

def calculate_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def archive_file(source_path, dest_dir, expected_hash, dest_filename=None):
    """
    Moves a file to G-Drive destination with hash verification and rollback.
    """
    try:
        if not os.path.exists(source_path):
            return {"status": "error", "message": f"Source not found: {source_path}"}
        
        # 1. Pre-Move Hash Verification
        pre_move_hash = calculate_hash(source_path)
        if pre_move_hash != expected_hash:
            return {"status": "error", "message": "Pre-move hash mismatch."}

        # Ensure destination directory exists
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        dest_file_name = dest_filename if dest_filename else os.path.basename(source_path)
        dest_path = os.path.join(dest_dir, dest_file_name)

        # 1.5 Collision Protection: Append (1), (2), etc. if file exists
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(dest_file_name)
            counter = 1
            while os.path.exists(os.path.join(dest_dir, f"{base} ({counter}){ext}")):
                counter += 1
            dest_file_name = f"{base} ({counter}){ext}"
            dest_path = os.path.join(dest_dir, dest_file_name)

        # 2. Copy and Verify (Rollback Logic: Move is a copy + delete)
        shutil.copy2(source_path, dest_path)
        
        # 3. Post-Move Hash Verification
        post_move_hash = calculate_hash(dest_path)
        if post_move_hash != expected_hash:
            # ROLLBACK
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return {"status": "error", "message": "Post-move hash mismatch. Rollback complete."}

        # 4. Finalize: Delete source only after full verification
        os.remove(source_path)

        return {
            "status": "success",
            "destination": dest_path,
            "hash": post_move_hash,
            "message": "File archived successfully with dual hash verification."
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Usage: archiver.py <source_path> <dest_dir> <expected_hash>"}))
        sys.exit(1)

    source = sys.argv[1]
    dest = sys.argv[2]
    expected = sys.argv[3]
    dest_filename = sys.argv[4] if len(sys.argv) > 4 else None
    
    result = archive_file(source, dest, expected, dest_filename)
    print(json.dumps(result))
