import os

def find_line_content(directory, line_number, content):
    for root, dirs, files in os.walk(directory):
        if any(exc in root for exc in ['.venv', 'venv', 'node_modules', '.git']):
            continue
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        if len(lines) >= line_number:
                            if content in lines[line_number - 1]:
                                print(f"Found in {path}: {lines[line_number - 1].strip()}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    find_line_content('.', 571, 'try:')
