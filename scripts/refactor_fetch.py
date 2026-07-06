import os
import re

def process_file(file_path):
    # Exclude tests and api.ts itself
    if '.test.' in file_path or 'api.ts' in file_path:
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    
    # 1. Replace fetch( with apiFetch( if fetch is used
    if 'fetch(' in content and 'apiFetch(' not in content:
        content = re.sub(r'\bfetch\(', 'apiFetch(', content)
        
        # Add import at the very top
        import_stmt = "import { apiFetch } from '@/lib/api'\n"
        if import_stmt not in content:
            content = import_stmt + content

    # 2. Replace hardcoded http://127.0.0.1:8765
    content = content.replace("http://127.0.0.1:8765/", "/")
    content = content.replace("http://127.0.0.1:8765", "")

    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")

def main():
    root_dir = 'src/renderer/src'
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.ts') or filename.endswith('.tsx'):
                process_file(os.path.join(dirpath, filename))

if __name__ == '__main__':
    main()
