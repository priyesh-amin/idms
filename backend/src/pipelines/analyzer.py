import sys
import json
import os

def analyze_context(content, about_me_path, okrs_path):
    """
    Analyzes document content against about-me.md and okrs.md to provide context.
    Returns a JSON response.
    """
    try:
        if not content:
            return {"status": "error", "message": "No content provided for analysis."}

        # Load context files
        context_data = ""
        if os.path.exists(about_me_path):
            with open(about_me_path, "r") as f:
                context_data += f.read() + "\n"
        
        if os.path.exists(okrs_path):
            with open(okrs_path, "r") as f:
                context_data += f.read() + "\n"

        # In a real implementation, this would involve sending the content + context to an LLM.
        # For this stateless script, we return the paths used and a placeholder for the orchestrator to fill.
        return {
            "status": "success",
            "context_files_read": [about_me_path, okrs_path],
            "analysis_placeholder": "LLM call required using this content and context."
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(json.dumps({"status": "error", "message": "Usage: analyzer.py <content> <about_me_path> <okrs_path>"}))
        sys.exit(1)

    content = sys.argv[1]
    about_me = sys.argv[2]
    okrs = sys.argv[3]
    
    result = analyze_context(content, about_me, okrs)
    print(json.dumps(result))
