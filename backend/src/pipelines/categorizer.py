import sys
import json
import re

def categorize_document(content):
    """
    Categorizes the document and extracts entity with intelligence.
    Implements weighted header analysis and signal detection.
    """
    try:
        if not content:
            return {"status": "error", "message": "No content provided."}

        # 1. Header Weighting (First 20% of text)
        header_limit = int(len(content) * 0.2)
        header_text = content[:header_limit]
        
        # 2. Entity Detection (Common Entities)
        entities = {
            "Toyota Financial Services": [r"Toyota Financial Services", r"Toyota Finance", r"Toyota Financial"],
            "Amex": [r"American Express", r"Amex", r"Onboarding Docs"],
            "Nandos": [r"Nandos", r"Nando's"],
            "National Parking Enforcement Providers": [r"National Parking Enforcement", r"NPE"],
            "HireRight": [r"HireRight", r"Background check"],
            "Queens Road Opticians": [r"Queens Road Opticians", r"optician"],
            "Metropolitan University": [r"Metropolitan University", r"Degree", r"Computing and Statistics"]
        }
        
        detected_entity = "Unknown"
        entity_conf = 0.0
        
        # Check header first (higher weight)
        for entity_name, patterns in entities.items():
            for pattern in patterns:
                if re.search(pattern, header_text, re.IGNORECASE):
                    detected_entity = entity_name
                    entity_conf = 0.98
                    break
            if detected_entity != "Unknown": break

        # Check full body if not in header
        if detected_entity == "Unknown":
            for entity_name, patterns in entities.items():
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        detected_entity = entity_name
                        entity_conf = 0.70
                        break
                if detected_entity != "Unknown": break

        # 3. Signal Detection for Doc Types
        # High value signals: any single match is a strong indicator
        high_value_signals = {
            "FinanceAgreementCompletion": [
                r"Agreement number", 
                r"Registration number", 
                r"Your agreement is complete",
                r"settlement",
                r"finance completion",
                r"completion letter"
            ],
            "Invoice": [
                r"VAT total",
                r"Invoice number",
                r"Tax Invoice"
            ],
            "Certificate": [
                r"Degree",
                r"Certificate",
                r"Honours",
                r"Computing and Statistics",
                r"conferred"
            ],
            "MedicalLetter": [
                r"Optician",
                r"Eye examination",
                r"Queens Road"
            ]
        }
        
        detected_type = "Document"
        type_conf = 0.1 # Base confidence for generic document
        
        # Scoring high value signals
        for doc_type, patterns in high_value_signals.items():
            matches = 0
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    matches += 1
            
            if matches > 0:
                # Even one match is a strong signal
                # 0.5 for 1 match, up to 0.9 for many
                score = 0.4 + (min(matches, 3) * 0.15)
                if score > type_conf:
                    detected_type = doc_type
                    type_conf = score

        # 4. Confidence Penalization & Refinement
        final_confidence = (entity_conf + type_conf) / 2
        
        # Penalize if invoice signals are missing but it's called an Invoice
        if detected_type == "Invoice":
            invoice_signals = [r"VAT", r"Invoice number", r"Line items"]
            found = sum(1 for s in invoice_signals if re.search(s, content, re.IGNORECASE))
            if found == 0:
                final_confidence *= 0.5
                detected_type = "Unclassified"

        # 5. Taxonomy Mapping
        category_map = {
            "FinanceAgreementCompletion": "05-financial",
            "Invoice": "05-financial",
            "Document": "00-uncategorized"
        }
        category = category_map.get(detected_type, "00-uncategorized")

        return {
            "status": "success",
            "entity": detected_entity,
            "doc_type": detected_type,
            "category": category,
            "confidence": round(final_confidence, 2),
            "entity_confidence": entity_conf,
            "type_confidence": type_conf,
            "signals_detected": [s for s in sum(high_value_signals.values(), []) if re.search(s, content, re.IGNORECASE)]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "No content provided."}))
        sys.exit(1)

    content = sys.argv[1]
    result = categorize_document(content)
    print(json.dumps(result))
