import os
import json
from extractor import extract_content

REVIEW_DIR = "00-daily-ops/Inbox/review"

def get_summary():
    files = [f for f in os.listdir(REVIEW_DIR) if f.endswith(".pdf")]
    summary = []
    for f in files:
        file_path = os.path.join(REVIEW_DIR, f)
        res = extract_content(file_path)
        if res['status'] == 'success':
            text = res['content']
            # Simple signal detection
            entity = "Unknown"
            if "Amex" in text or "American Express" in text: entity = "Amex"
            elif "Nando" in text: entity = "Nandos"
            elif "Toyota" in text: entity = "Toyota"
            elif "National Parking" in text or "NPE" in text: entity = "NPE"
            
            doc_type = "Document"
            if "Invoice" in text: doc_type = "Invoice"
            elif "Agreement" in text: doc_type = "Agreement"
            elif "Consent" in text: doc_type = "ConsentForm"
            elif "Non-disclosure" in text or "NDA" in text: doc_type = "NDA"
            
            summary.append({
                "filename": f,
                "hash": res['hash'],
                "entity": entity,
                "type": doc_type,
                "snippet": text[:300].replace("\n", " ").strip()
            })
    return summary

if __name__ == "__main__":
    s = get_summary()
    for item in s:
        print(f"--- {item['filename']} ---")
        print(f"Hash: {item['hash']}")
        print(f"Proposed: {item['entity']} / {item['type']}")
        print(f"Snippet: {item['snippet']}")
        print("")
