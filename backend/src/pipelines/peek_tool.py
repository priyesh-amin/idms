import sys
import json
import os

def peek_content(file_path):
    from extractor import extract_content
    result = extract_content(file_path)
    if result['status'] == 'success':
        print(json.dumps({
            'hash': result['hash'],
            'peek': result['content'][:1000]
        }))
    else:
        print(json.dumps(result))

if __name__ == "__main__":
    peek_content(sys.argv[1])
