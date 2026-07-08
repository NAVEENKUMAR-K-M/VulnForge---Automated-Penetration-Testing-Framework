import os

replacements = {
    '0001_initial_schema.py': [
        ('sa.Enum("admin", "analyst", "viewer", name="user_role_enum")', 'user_role_enum'),
        ('sa.Enum("host", "network", "url", "domain", name="target_type_enum")', 'target_type_enum'),
        ('sa.Enum("reconnaissance", "vulnerability_scanning", "exploitation", "post_exploitation", name="plugin_phase_enum")', 'plugin_phase_enum'),
        ('sa.Enum("pending", "running", "paused", "completed", "failed", "cancelled", name="scan_status_enum")', 'scan_status_enum'),
        ('sa.Enum("reconnaissance", "vulnerability", "exploitation", "full", name="scan_type_enum")', 'scan_type_enum'),
        ('sa.Enum("low", "medium", "high", "critical", name="priority_enum")', 'priority_enum'),
        ('sa.Enum("pending", "running", "completed", "failed", "skipped", "timed_out", name="plugin_exec_status_enum")', 'plugin_exec_status_enum'),
        ('sa.Enum("info", "low", "medium", "high", "critical", name="vuln_severity_enum")', 'vuln_severity_enum'),
        ('sa.Enum("open", "confirmed", "false_positive", "mitigated", "resolved", name="vuln_status_enum")', 'vuln_status_enum'),
        ('sa.Enum("cve", "cwe", "url", "advisory", "exploit_db", name="ref_type_enum")', 'ref_type_enum'),
        ('sa.Enum("executive_summary", "technical", "compliance", name="report_type_enum")', 'report_type_enum'),
        ('sa.Enum("html", "pdf", "json", name="report_format_enum")', 'report_format_enum'),
        ('sa.Enum("pending", "generating", "completed", "failed", name="report_status_enum")', 'report_status_enum'),
    ],
    '0003_add_workspace_tables.py': [
        ('sa.Enum("active", "completed", "archived", name="workspace_status_enum")', 'workspace_status_enum'),
        ('sa.Enum("owner", "member", "viewer", name="workspace_member_role_enum")', 'workspace_member_role_enum'),
    ],
    '0005_add_scope_rules_table.py': [
        ('create_type=True', 'create_type=False'),
        ('down_revision: str = "0004"', 'down_revision: str = "0004_add_workspace_id_to_scans"'),
    ],
    '0006_add_scan_profiles_tables.py': [
        ('create_type=True', 'create_type=False'),
    ],
    '0007_add_discovered_assets.py': [
        ('create_type=True', 'create_type=False'),
    ]
}

base_dir = r'd:\VulnForge\backend\alembic\versions'

for filename, reps in replacements.items():
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for old, new in reps:
            content = content.replace(old, new)
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filename}")
