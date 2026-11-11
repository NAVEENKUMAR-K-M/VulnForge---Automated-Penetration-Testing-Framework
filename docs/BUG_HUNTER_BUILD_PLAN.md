# VulnForge — Bug-Hunter Build: Continuation Plan

> **Purpose:** resume the "turn VulnForge into a real bug hunter" build after a PC
> reset. This doc is self-contained: environment setup, what's done, what's left,
> conventions, and how to validate. Last updated 2026-11-11.

- **Branch:** `feat/agent-ui-and-polish` (all work below is here, **not merged to `main`**).
- **Remote:** `https://github.com/NAVEENKUMAR-K-M/VulnForge---Automated-Penetration-Testing-Framework`
- **Latest relevant commit:** `c99dcd7` (slice 4/7).

---

## 0. TL;DR — where we are

The bug-hunter toolkit is being built in **7 vertical slices**. **Slices 1–4 are
done, tested, committed, and pushed.** The core loop works end-to-end:
**crawl → actively test → findings with captured evidence**, including behind login.

| # | Slice | Status | Commit |
|---|-------|--------|--------|
| 1 | HTTP attack-surface model (endpoints + transactions) | ✅ done | `d54b806` |
| 2 | Web crawler (maps endpoints, params, forms) | ✅ done | `ce96bf5` |
| 3 | Active scanner — reflected XSS / error-based SQLi / open redirect + evidence | ✅ done | `2e561b5` |
| 4 | Authenticated crawling & scanning (static creds or form login) | ✅ done | `c99dcd7` |
| 5 | **OAST** — out-of-band listener for blind SSRF/XSS/RCE | ⬜ **next** | — |
| 6 | **Verification loop** — re-fire a finding's probe to confirm (kill false positives) | ⬜ todo | — |
| 7 | **Deep per-finding agent loop** + JS/OpenAPI discovery inputs | ⬜ todo | — |

Also already done earlier this session (context): the full **"Signal" light UI
redesign** and a **green test suite** (308 passed) which fixed **3 real bugs**
(see `docs`/git log and the memory file `baseline-test-failures.md`).

---

## 1. Resume checklist after a PC reset

1. **Clone + branch**
   ```bash
   git clone https://github.com/NAVEENKUMAR-K-M/VulnForge---Automated-Penetration-Testing-Framework.git
   cd VulnForge---Automated-Penetration-Testing-Framework
   git checkout feat/agent-ui-and-polish
   ```
2. **Install Docker Desktop** (Windows/Mac) or Docker Engine. The whole stack runs in Compose.
3. **Secrets** — these are **gitignored** and were NOT committed; re-create `.env`
   (or the env block compose reads) with your own keys:
   - `VOYAGE_API_KEY` (embeddings) — Voyage AI.
   - `GITHUB_PAT` / `HACKERONE_API_TOKEN` (optional RAG source connectors).
   - `FIRST_SUPERUSER_PASSWORD` is `CHANGE_ME_ADMIN_PASSWORD_12345` in compose (change it).
   - **Never commit keys.** Secret-scan every commit for `pa-…` (Voyage) and `github_pat_…`.
4. **Bring up the stack**
   ```bash
   docker compose up -d        # api, db (pgvector/pg15), redis, celery-worker, frontend
   docker compose exec api alembic upgrade head   # apply migrations (incl. 0011 web surface)
   ```
   - Frontend: http://localhost:5173  ·  API: http://localhost:8000
   - Login: `admin@vulnforge.com` / `CHANGE_ME_ADMIN_PASSWORD_12345`
5. **Provision the test database** (integration tests need a container-reachable DB):
   ```bash
   docker compose exec db psql -U vulnforge_user -d vulnforge -c "CREATE DATABASE vulnforge_test;"
   # extensions get created by migrations; the test fixture resets + migrates each run
   ```
6. **Run the suite** (see §6).

---

## 2. What's built (slices 1–4) — file map

**Slice 1 — data model** (the foundation everything else writes to):
- `backend/app/models/web.py` — `HttpEndpoint` (dedup'd per workspace+method+url,
  with `parameters`/`source_tools`/`metadata`/`requires_auth`) and
  `HttpTransaction` (append-only request/response evidence, FK-linkable to an
  endpoint and the vulnerability it proves). Enums: `HttpMethod`,
  `ParameterLocation`, `TransactionSource`.
- `backend/alembic/versions/0011_add_web_surface.py` — tables + enums.
- `backend/app/schemas/web.py` — `HttpEndpointCreate/Response`,
  `HttpTransactionCreate/Response`, `EndpointParameter`.
- `backend/app/repositories/web.py` — `EndpointRepository.ingest_endpoints`
  (on-conflict merge of tools/params/metadata) + `list_endpoints`;
  `TransactionRepository.add_transactions` (resolves endpoint by URL) + `list_transactions`.
- Wiring: `ParsedResults` (in `backend/app/schemas/plugin.py`) now carries
  `endpoints` + `transactions`; `backend/app/tasks/scan_tasks.py` ingests them per plugin.

**Slice 2 — crawler:**
- `backend/app/plugins/reconnaissance/web_crawler/crawler.py` — **shared** crawl
  routine `crawl_site(...)` (same-host BFS, link + `<form>` extraction → endpoints
  with params, transaction capture). Also the **auth helpers** (slice 4): `make_client`, `apply_auth`.
- `backend/app/plugins/reconnaissance/web_crawler/plugin.py` — `WebCrawlerPlugin`
  (thin; delegates to `crawl_site`).

**Slice 3 — active scanner:**
- `backend/app/plugins/vulnerability_scanning/web_active_scan/plugin.py` —
  `WebActiveScanPlugin`. Crawls, then injects probes into every parameter:
  reflected XSS (CWE-79), error-based SQLi (CWE-89), open redirect (CWE-601).
  Each hit → `VulnerabilityCreate` + a **DAST `HttpTransaction` evidence row**.
  `VULNERABILITY_SCANNING` phase ⇒ the orchestrator treats it as an **ACTIVE**
  tool requiring human approval.

**Slice 4 — authenticated scanning:**
- `make_client()` carries static `headers`/`cookies`; `apply_auth()` performs an
  optional **form login** (`login_url`/`login_method`/`login_data`) so session
  cookies stick. `crawl_site(..., auth=…)` and both plugins expose an `auth` config.

**Tests:** `backend/tests/unit/test_plugins/{test_web_crawler,test_web_active_scan,test_web_auth}.py`
and `backend/tests/integration/repositories/test_web_repo.py`.

---

## 3. Remaining slices — detailed plan

### Slice 5 — OAST (out-of-band application security testing) — **next**
**Why:** blind SSRF, blind XSS, blind RCE and OOB SQLi produce **no response
signal** — you need an external callback channel. This is the biggest remaining
piece (new long-lived service).

**Plan:**
1. **Interaction listener service.** Either integrate **interactsh** (projectdiscovery)
   via its client, or build a minimal first-party listener: a small FastAPI/aiohttp
   service with a wildcard DNS/HTTP catch-all that records inbound hits
   (`{correlation_id, source_ip, proto, timestamp, raw}`). Add it as a
   `oast` service in `docker-compose.yml`.
2. **Data model:** `oast_interactions` table (migration `0012`) +
   `OastInteraction` model (workspace_id, correlation_id, scan_id, type, source_ip,
   raw, created_at). Repository + schema.
3. **Payload mint + poll API:** a service that mints unique correlation subdomains/URLs
   (`<id>.oast.<domain>`) and a poll endpoint to fetch interactions by correlation id.
4. **Wire into the active scanner:** add blind probes — SSRF (inject OAST URL into
   url-ish params + headers like `X-Forwarded-For`/`Referer`), blind XSS (store OAST
   `<script src>` payloads), OOB SQLi — then **poll** after the run; any interaction
   ⇒ a confirmed finding with the interaction as evidence.
5. **Agent tool:** expose minting + polling as an agent tool so the orchestrator can
   use OAST in its loop.

**Gotcha:** OAST needs a reachable domain/IP for real targets. For the **lab**, point
payloads at the in-network listener hostname (e.g. `http://vf-oast/<id>`), which the
lab app can reach — enough to validate end-to-end without public DNS.

### Slice 6 — Verification loop (lighter; do first if you want a quick win)
**Why:** kill false positives; raise confidence on real ones.
**Plan:**
1. Add a `confidence`/`verified` concept to findings (the `Vulnerability` model already
   has `verified_by_id`/`verified_at`; add an auto-verification path).
2. A `VerificationService` (or a post-scan step) that **re-fires the stored probe**
   from a finding's evidence transaction and re-checks the signal (XSS marker still
   reflected, SQL error still present, redirect still happens). Mark verified/unverified,
   store a second `verification` `HttpTransaction`.
3. Optional: a diff/baseline to suppress findings present in a clean baseline response.
4. Expose a "re-verify" action on the finding in the API + UI.

### Slice 7 — Deep per-finding agent loop + discovery inputs (most complex)
**Why:** the current orchestrator does *tool selection*; it doesn't *work a single bug*.
**Plan:**
1. **Discovery inputs:** JS endpoint extraction (regex/AST over fetched `.js` to find
   paths + params) and OpenAPI/GraphQL ingestion (parse a schema → seed endpoints).
   Add as reconnaissance plugins feeding the Slice-1 endpoint table.
2. **Per-finding agent sub-loop:** given one candidate finding, the agent runs a
   **hypothesis → craft request → observe → refine** loop (bounded, scope-gated,
   approval-gated for active steps), using the LLM + RAG writeups for payload ideas,
   capturing each attempt as a transaction. Chain related findings.
3. Surface the reasoning trace + evidence in the Agent UI.

---

## 4. Conventions — how to add a plugin

- Inherit `app/core/plugin_base.py:BasePlugin`. Define a `manifest = PluginManifest(...)`
  with a unique `name`, a `phase` (`RECONNAISSANCE` = passive tier; others = active tier
  for the agent's approval gate), and `default_config`.
- Implement `check_dependencies()` (return False to SKIP gracefully),
  `execute() -> PluginExecutionResult` (do the work; serialize to `raw_output`),
  `parse_results(raw) -> ParsedResults` (pure; map to `VulnerabilityCreate` /
  `AssetCreate` / `HttpEndpointCreate` / `HttpTransactionCreate`).
- Put it under `app/plugins/<phase>/<name>/{__init__.py exports the class, plugin.py}`.
  The `PluginLoader` auto-discovers it; the lifespan sync registers it in the DB on
  API startup (restart the api container to pick up a new plugin for scan profiles).
- Pure-Python plugins (like the crawler/scanner) need no external binary — prefer this.

---

## 5. Validating a web plugin against a lab target (the pattern used here)

The stack's `db` network is `vulnforge---automated-penetration-testing-framework_default`.
Spin a throwaway target on it and drive the plugin from the `api` container:

```bash
NET=$(docker network ls --format '{{.Name}}' | grep -i vulnforge | head -1)
docker run -d --name vf-lab --network "$NET" python:3.11-alpine sleep 3600
docker exec -i vf-lab sh -c 'cat > /app.py' <<'PY'
# ... a tiny http.server app that reflects a param / errors on ' / redirects ...
PY
docker exec -d vf-lab sh -c 'python /app.py > /tmp/a.log 2>&1'
# then, inside the api container, instantiate the plugin against http://vf-lab and print parse_results()
docker rm -f vf-lab   # clean up when done
```

> DVWA (`ghcr.io/digininja/dvwa`) needs its own MariaDB; standalone it just errors.
> For quick validation, the tiny purpose-built apps above are faster and deterministic.

---

## 6. Running tests

```bash
# Unit (fast, no DB needed for most):
docker compose exec api python -m pytest --no-cov -o addopts="" tests/unit/

# Integration (needs the test DB; fixture resets + runs real migrations):
docker compose exec -e TEST_POSTGRES_HOST=db -e TEST_POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD \
  -e TEST_REDIS_HOST=redis api python -m pytest --no-cov -o addopts="" tests/integration/

# Everything:
docker compose exec -e TEST_POSTGRES_HOST=db -e TEST_POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD \
  -e TEST_REDIS_HOST=redis api python -m pytest --no-cov -o addopts="" tests/
```

Notes:
- `--no-cov -o addopts=""` disables the 80% coverage gate (it otherwise "fails" a run).
- The integration fixture builds schema via **Alembic migrations** (NOT
  `metadata.create_all`, which can't create the partitioned `audit_logs` table) and
  is **env-overridable** (`TEST_POSTGRES_*`). See `backend/tests/conftest.py`.
- Baseline before this session's fixes was red; it is now **308 passing**.

---

## 7. Gotchas / things that bit us

- **Settings override in tests:** the app resolves settings via `get_settings_dep`
  (not `get_settings`), so test overrides must target `get_settings_dep`. Already fixed.
- **`.local` emails** are rejected by `email-validator`; use a real TLD in tests.
- **Targets are global** (no `workspace_id` column) — linked via `workspace_targets`.
  Scope vuln/endpoint queries by joining `WorkspaceTarget`.
- **Frontend design:** stay in the **"Signal"** light system — never reintroduce
  violet, aurora blobs, gradient text, or heavy glassmorphism. Tokens in
  `frontend/src/index.css`. (See memory `ui-design-preference.md`.)

---

## 8. Other open items (outside the 7 slices)

- **Merge `feat/agent-ui-and-polish` → `main`** once you're happy (UI redesign + test
  fixes + web slices all live here).
- **Password-reset email dispatch** — `backend/app/api/v1/auth.py` has a `TODO`: it
  mints the reset token but never sends the email.
- **Phase 3 live validation** — AI executive summary via the real CLI LLM provider
  in Docker (works via deterministic fallback; never exercised with a live LLM).
- **Phase 4 live validation** — run the orchestrator agent against a lab target and
  confirm the approval gate / scope-stop / audit trail fire.

---

*Resume point: start Slice 5 (OAST), or Slice 6 (verification) for a lighter win first.*
