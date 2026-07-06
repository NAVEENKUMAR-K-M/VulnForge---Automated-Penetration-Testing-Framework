$packages = @(
    "backend/app",
    "backend/app/api",
    "backend/app/api/v1",
    "backend/app/core",
    "backend/app/models",
    "backend/app/schemas",
    "backend/app/repositories",
    "backend/app/services",
    "backend/app/database",
    "backend/app/utils",
    "backend/app/parsers",
    "backend/tests",
    "backend/tests/unit",
    "backend/tests/unit/test_services",
    "backend/tests/unit/test_repositories",
    "backend/tests/unit/test_parsers",
    "backend/tests/unit/test_utils",
    "backend/tests/integration",
    "backend/tests/integration/test_api",
    "backend/tests/integration/test_database",
    "plugins",
    "plugins/base",
    "plugins/reconnaissance",
    "plugins/reconnaissance/nmap",
    "plugins/reconnaissance/shodan",
    "plugins/vulnerability_scanning",
    "plugins/vulnerability_scanning/nuclei",
    "plugins/vulnerability_scanning/nikto",
    "plugins/exploitation",
    "plugins/exploitation/metasploit",
    "plugins/exploitation/sqlmap",
    "plugins/post_exploitation",
    "plugins/post_exploitation/credential_harvesting",
    "reports",
    "reports/renderers",
    "reports/exporters"
)

foreach ($p in $packages) {
    $initFile = Join-Path $p "__init__.py"
    if (-not (Test-Path $initFile)) {
        New-Item -ItemType File -Path $initFile -Force | Out-Null
    }
}

$rootFiles = @(".env.example", ".gitignore", ".dockerignore", "Makefile", "README.md")
foreach ($f in $rootFiles) {
    if (-not (Test-Path $f)) {
        New-Item -ItemType File -Path $f -Force | Out-Null
    }
}

Write-Host "All init and root files created successfully."
