# Developer & Contribution Guide

We welcome contributions to VulnForge! Whether you're fixing a bug, adding a new UI component, or building a brand new Recon Plugin, this guide will help you navigate the codebase.

## 1. Setting up the Development Environment

Please follow the "Method 2: Bare Metal" instructions in the [Installation Guide](INSTALLATION.md) to set up your local development servers.

### Formatting & Linting
We enforce strict code formatting.
- **Backend**: Uses `Black` and `Ruff`.
  - To format code: `black app tests`
  - To lint: `ruff check app tests`
- **Frontend**: Uses `Oxlint` for blazing-fast JavaScript/TypeScript linting.
  - To lint: `npm run lint`

## 2. Writing Backend Tests

VulnForge uses `pytest` with a robust architecture for automated testing. Our CI/CD pipeline requires tests to pass before merging.

### Running Tests
To execute the entire test suite and generate an HTML coverage report:
```bash
pytest --cov=app --cov-report=html tests/
```
Open `backend/coverage_html/index.html` in your browser to view exactly which lines of code you need to test.

### Test Architecture
- **Unit Tests** (`tests/unit/`): Use `unittest.mock.AsyncMock` to isolate services. Never hit the database here.
- **Integration Tests** (`tests/integration/`): These hit a live PostgreSQL testing database (`vulnforge_test`). The `conftest.py` ensures that every test runs inside a rolled-back transaction to prevent state pollution.

## 3. Creating a New Recon Plugin

VulnForge's Recon Engine is highly modular. To add a new scanning tool (e.g., `Amass`, `Nikto`):

1. **Create the Plugin File**: Navigate to `backend/app/plugins/` and create a new Python file (e.g., `amass_plugin.py`).
2. **Inherit from `BasePlugin`**:
   ```python
   from app.core.plugin_base import BasePlugin, ParsedResults

   class AmassPlugin(BasePlugin):
       @property
       def name(self) -> str:
           return "Amass"
           
       async def execute(self) -> str | None:
           # Execute the CLI binary asynchronously
           return await self._run_subprocess(["amass", "enum", "-d", self.target])
           
       def parse(self, raw_output: str) -> ParsedResults:
           # Parse the raw JSON/Text output into VulnForge schemas
           results = ParsedResults()
           # ... append Asset findings
           return results
   ```
3. **Register the Plugin**: The application will automatically discover your plugin on startup if it inherits `BasePlugin`!

## 4. Submitting a Pull Request
- Create a new branch: `git checkout -b feature/your-feature-name`
- Write tests for your changes.
- Ensure all linting passes.
- Submit the PR with a clear description of the problem solved.
