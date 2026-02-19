import os
import json
import sys
from extractor import extract_content

REVIEW_DIR = "00-daily-ops/Inbox/review"

def peek_all():
    files = [f for f in os.listdir(REVIEW_DIR) if f.endswith(".pdf")]
    results = []
    for f in files:
        file_path = os.path.join(REVIEW_DIR, f)
        res = extract_content(file_path)
        if res['status'] == 'success':
            results.append({
                'filename': f,
                'hash': res['hash'],
                'peek': res['content'][:500]
            })
        else:
            results.append({
                'filename': f,
                'status': 'error',
                'message': res['message']
            })
    print(json.dumps(results))

if __name__ == "__main__":
    peek_all()
