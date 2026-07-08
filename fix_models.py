import os, glob, re

base_dir = r'd:\VulnForge\backend\app\models'
for path in glob.glob(os.path.join(base_dir, '*.py')):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def replacer(match):
        m = match.group(0)
        if 'values_callable' in m:
            return m
        return m.replace('name=', 'values_callable=lambda obj: [e.value for e in obj], name=')
        
    new_content = re.sub(r'Enum\([^)]*name=\"[^\"]+\"[^)]*\)', replacer, content)
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Fixed {path}')
