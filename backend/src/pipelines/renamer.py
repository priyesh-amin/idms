import sys
import json
from datetime import datetime

def generate_filename(doc_type, entity, detail, extension="pdf", date_str=None):
    """
    Generates a filename based on the YYYY-MM-DD_<DocType>_<Entity>_<Detail>.pdf format.
    """
    try:
        if not date_str:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Sanitize inputs
        doc_type = doc_type.replace(" ", "-").capitalize()
        entity = entity.replace(" ", "-")
        detail = detail.replace(" ", "-")
        
        filename = f"{date_str}_{doc_type}_{entity}_{detail}.{extension}"
        return {"status": "success", "filename": filename}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Usage: renamer.py <DocType> <Entity> <Detail> [extension]"}))
        sys.exit(1)

    doc_type = sys.argv[1]
    entity = sys.argv[2]
    detail = sys.argv[3]
    extension = sys.argv[4] if len(sys.argv) > 4 else "pdf"
    date_val = sys.argv[5] if len(sys.argv) > 5 else None
    
    result = generate_filename(doc_type, entity, detail, extension, date_val)
    print(json.dumps(result))
