import subprocess
import json
import os
import sys

SCRIPTS_DIR = "00-daily-ops/scripts/idms"
REVIEW_DIR = "00-daily-ops/Inbox/review"
PIPELINE_RUNNER = os.path.join(SCRIPTS_DIR, "pipeline_runner.py")

# Map of filenames to their approved categories
MAPPING = {
    "Amex - Consent and Authorisation.pdf": "Amex onboarding",
    "Amex Gmail - We've received your information – further steps may be required.pdf": "Amex onboarding",
    "Amex Screening Disclosure and Authorization.pdf": "Amex onboarding",
    "Amex date format issue Gmail - AMEX Onboarding Docs_Priyesh Amin.pdf": "Amex onboarding",
    "BVC Amex UnsignedDocument.pdf": "Amex onboarding",
    "NDA CORRECT DATE FORMAT V2.pdf": "Amex onboarding",
    "Nandos - £60 NPE - National Parking Enforcement Providers.pdf": "fines",
    "Non-disclosure agreement.pdf": "Amex onboarding",
    "Priyesh Amin - Bsc Honours Computing and Statistics Certificate.pdf": "credentials",
    "Scan2026-02-17_112650.pdf": "01-medical",
    "nda correct date format.pdf": "Amex onboarding"
}

def apply_review():
    for filename, category in MAPPING.items():
        file_path = os.path.join(REVIEW_DIR, filename)
        if not os.path.exists(file_path):
            print(f"Skipping {filename}: Not found in review folder.")
            continue
            
        overrides = json.dumps({"category": category, "confidence": 1.0})
        cmd = [sys.executable, PIPELINE_RUNNER, "--file", file_path, "--overrides", overrides]
        
        print(f"Processing {filename} -> {category}...")
        try:
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
            print(result)
        except subprocess.CalledProcessError as e:
            print(f"Error processing {filename}:")
            print(e.output.decode('utf-8'))

if __name__ == "__main__":
    apply_review()
