import os, glob, re

migrations_dir = r'd:\VulnForge\backend\alembic\versions'
files = glob.glob(os.path.join(migrations_dir, '*.py'))

for path in files:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to replace `name="something_enum",\n    )` with `name="something_enum",\n        create_type=False,\n    )`
    # Or just `name="something_enum")` -> `name="something_enum", create_type=False)`
    
    # Safest way using regex that looks for name="..." and doesn't have create_type=False
    def replacer(match):
        m = match.group(0)
        if "create_type=False" in m:
            return m
        return m.replace(match.group(1), match.group(1) + ", create_type=False")
        
    new_content = re.sub(r'(name=\"\w+\")', replacer, content)
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {path}")
