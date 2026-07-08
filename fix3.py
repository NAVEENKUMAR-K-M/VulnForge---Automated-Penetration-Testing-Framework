import os, glob, re

for path in glob.glob(r'd:\VulnForge\backend\alembic\versions\*.py'):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to replace `postgresql.ENUM(..., name="foo_enum", ...)` inside sa.Column
    # with just `foo_enum`
    
    def replacer(match):
        inner_text = match.group(1)
        # find name="..."
        m_name = re.search(r'name=\"(\w+)\"', inner_text)
        if m_name:
            enum_name = m_name.group(1)
            return enum_name
        return match.group(0)

    # regex to match postgresql.ENUM(...) or sa.Enum(...)
    new_content = re.sub(r'(?:postgresql|sa)\.ENUM\((.*?)\)', replacer, content, flags=re.DOTALL)
    new_content = re.sub(r'sa\.Enum\((.*?)\)', replacer, new_content, flags=re.DOTALL)
    
    # But wait, the definitions at the top ALSO match this!
    # e.g. user_role_enum = postgresql.ENUM(...)
    # I ONLY want to replace it if it's INSIDE sa.Column!
    
    # So let's match sa.Column(...) and process its contents
    def column_replacer(match):
        col_content = match.group(1)
        # inside col_content, replace ENUMs
        col_content = re.sub(r'(?:postgresql|sa)\.ENUM\((.*?)\)', replacer, col_content, flags=re.DOTALL)
        col_content = re.sub(r'sa\.Enum\((.*?)\)', replacer, col_content, flags=re.DOTALL)
        return f"sa.Column({col_content})"

    new_content = re.sub(r'sa\.Column\((.*?)\)', column_replacer, content, flags=re.DOTALL)
    
    # Wait, sa.Column(...) can span multiple lines, but regex with .*? is greedy across nested parens if we aren't careful.
    # Actually, a much safer way is to just look for `sa.Column("role", postgresql.ENUM(..., name="user_role_enum", ...)`
    # and replace the Enum part.

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Fixed {path}')
