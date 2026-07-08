import os, glob, re

migrations_dir = r'd:\VulnForge\backend\alembic\versions'
files = glob.glob(os.path.join(migrations_dir, '*.py'))

for path in files:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(
        r'sa\.Enum\((.*?name=\".*?\")\)', 
        r'postgresql.ENUM(\1, create_type=False)', 
        content
    )
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {path}")
