import os
import json
import sys
import subprocess

SCRIPTS_DIR = "00-daily-ops/scripts/idms"
PIPELINE_RUNNER = os.path.join(SCRIPTS_DIR, "pipeline_runner.py")

SURVIVORS = [
    "06-long-term-memory/Amex onboarding/2026-02-17_Document_Amex_Import.pdf",
    "06-long-term-memory/Amex onboarding/2026-02-17_Document_Unknown_Import.pdf",
    "06-long-term-memory/fines/2026-02-17_Document_National-Parking-Enforcement-Providers_Import.pdf",
    "06-long-term-memory/credentials/2026-02-17_Document_Unknown_Import.pdf",
    "06-long-term-memory/01-medical/2026-02-17_Document_Unknown_Import.pdf"
]

def fix_survivors():
    for rel_path in SURVIVORS:
        file_path = rel_path # rel to workspace root
        if not os.path.exists(file_path):
            print(f"Not found: {file_path}")
            continue
            
        print(f"Re-processing {file_path}...")
        # Since we want to RENAME in place, we'll use overrides for category (keep same) but let orchestrator find entity/type
        # We need to know the category to pass it as override so it doesn't move to 00-uncategorized if categorizer fails
        category = rel_path.split('/')[1]
        
        overrides = json.dumps({"category": category, "confidence": 1.0})
        cmd = [sys.executable, PIPELINE_RUNNER, "--file", file_path, "--overrides", overrides]
        
        try:
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
            print(result)
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.output.decode('utf-8')}")

if __name__ == "__main__":
    fix_survivors()
