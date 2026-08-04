# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

AuditForge is an AI-assisted **post-scan** triage and audit-reporting system (Kerja Praktik project at PT Suryasoft Konsultama). It ingests security-tool output (Nuclei, ZAP, Nmap, Burp, SARIF), normalizes/dedupes/enriches/triages findings deterministically, has an LLM draft narratives + executive summaries, then auditors review/edit/approve, and DOCX/PDF reports are assembled from approved findings only. It never scans or exploits anything.

Two invariants that shape almost every design decision:

1. **AI only drafts; the auditor is the final decision-maker.** Everything non-AI (parse → normalize → enrichment → dedup → triage → masking → report assembly → eval metrics) is **deterministic** and tested without any LLM call. Reports contain only human-approved findings; the auditor's final narrative always wins over the AI draft.
2. **Sensitive data is masked before it ever leaves the machine.** All feature LLM calls go through `app/ai/llm.py:draft()`, which masks the prompt (internal IPs/hosts, credentials, keys, emails → `[IP-INTERNAL-1]`, `[HOST-1]`, `[SECRET-1]`, …) and unmasks the reply server-side. The placeholder map never leaves. Do not call providers directly from feature code — always go through `draft()`. Guarantees are tested in `tests/test_security.py` / `tests/test_masking.py`.

## Running

Docker Compose is the only supported way to run the full stack (`name: auditforge`, so containers are `auditforge-<service>-1`):

```bash
cp .env.example .env
docker compose up --build
```

Services: `web` (Next.js :3000), `api` (FastAPI :8000), `worker` + `beat` (Celery), `postgres` :5432, `redis` :6379, `minio` :9000 (console on **:9101**, not 9001). Web proxies `/api/*` to `api` same-origin (see `frontend/next.config.mjs`) — no CORS needed for the browser path; only port 3000 need be exposed for a public demo.

Login is by **email** (not username). Seed admin: `admin@auditforge.local` / `admin12345`; re-seed with `docker exec auditforge-api-1 python -m app.scripts.seed` (idempotent).

## Commands

Run tooling **inside the containers**. The image installs `pip install -e .` only — **dev tools are not baked in**, so install the extras first (and again after any `docker compose build`, which discards them):

```bash
docker exec auditforge-api-1 pip install -e ".[dev]"        # pytest + ruff + mypy

# Backend
docker exec auditforge-api-1 python -m pytest -q                 # full suite (~3s, 109 tests)
docker exec auditforge-api-1 python -m pytest tests/test_triage.py -q          # one file
docker exec auditforge-api-1 python -m pytest tests/test_triage.py::test_name  # one test
docker exec auditforge-api-1 alembic upgrade head                # DB migrations
docker exec auditforge-api-1 python -m app.eval.run              # D12 eval harness → eval_data/report.json

# Frontend
docker exec auditforge-web-1 npx tsc --noEmit                    # typecheck (currently clean)
# Do NOT run `npm run lint` — no ESLint config exists, so `next lint` hangs on an
# interactive setup prompt. `tsc --noEmit` is the only frontend gate.
```

**pytest is the real gate.** The suite is pure unit tests — no DB, Redis, MinIO, or LLM, and no `conftest.py`; LLM providers are stubbed with `monkeypatch`. Keep new tests that way: exercise the deterministic modules directly, fake ORM rows with `SimpleNamespace` (see `tests/test_reporting.py`), and never let a test require live infrastructure.

Sample tool output for tests lives in **`datasets/fixtures/`** (`nuclei-sample.jsonl`, `nmap-sample.xml`, `broken-sample.xml`, …), not under `backend/tests/`. Add new parser fixtures there.

`ruff check .` and `mypy app` run but **do not pass on a clean tree** (~189 and ~33 findings respectively). The ruff noise is dominated by `EXE002` (Windows bind-mount marks every file executable) and `B008` (FastAPI's `Depends()` default-argument idiom) — `pyproject.toml` pins no explicit `[tool.ruff.lint] select`, so the installed ruff picks a very wide default ruleset. Treat both as baselines: diff before/after your change rather than reading the totals as regressions you introduced, and don't bulk-"fix" pre-existing hits unless asked.

`npm run lint` is **not** usable — no ESLint config exists, so `next lint` stops on an interactive setup prompt. Use `tsc --noEmit`.

**After changing Celery task code you must restart the `worker` (and `beat`) container** — it does not hot-reload like the API.

## Code conventions

- **Docstrings and comments are written in Indonesian**; identifiers, types, and API field names are English. Match that when editing — don't convert existing Indonesian prose to English, and don't rename symbols to Indonesian.
- Modules and tests are tagged with requirement IDs from the design docs (`D7` dedup, `D8` enrichment, `D10` narrative, `D11` triage + exec summary, `D12` eval, `D13` review, `D15` reporting, `D17` security, `R3` auto-ingest). Preserve these tags; they are how code traces back to the spec.
- Background tasks catch broad exceptions deliberately (`# noqa: BLE001`) and return the failure as data — a bad upload or a dead LLM must never crash the worker or abort a batch.
- Domain enums live in `models/enums.py` but are stored as plain `String` columns; validation happens in the app layer, not the DB.

## Architecture

### Backend (`backend/app/`) — FastAPI + Celery, deterministic core

The processing pipeline lives largely in `workers/tasks.py` and is the best entry point to understand the system. `parse_upload` orchestrates the deterministic path in a fixed order, and that order matters:

```
parse (parsers/) → per-finding enrichment (enrichment.py) → fingerprint + dedup (normalize.py)
  → store/merge Finding rows → deterministic triage P1–P4 (triage.py)
```

- **`parsers/`** — `BaseParser` + one subclass per tool (`nuclei`, `zap`, `nmap`, `burp`, `sarif`). `select_parser()` auto-detects the tool via `sniff()` when the upload's `tool` is `unknown`/auto, so tool choice on upload is optional. All parsers emit a `UnifiedFinding`.
- **`normalize.py`** — collapses each tool's severity into one scale (critical/high/medium/low/info via `severity_rank`), and computes the dedup `fingerprint`. Enrichment happens **before** fingerprinting so equivalent findings across tools/files merge.
- **Dedup semantics** (`_ingest_findings` in tasks.py): same fingerprint → merge (highest severity/CVSS wins, record `sources`, bump `occurrences`, union CVEs); dedup is **cross-file and cross-tool within one engagement**. Merges reassign list columns (`row.cve = [...]`) rather than mutating them, so SQLAlchemy detects the change — keep that pattern.
- **`enrichment.py`** — maps to CWE + OWASP Top 10, computes CVSS v3.1, links CVEs. Severity from CVSS can only **raise** a tool's label, never lower it.
- **`triage.py`** — deterministic P1–P4 from severity + CVSS + occurrences + CVE. Re-applied to every finding in the engagement after each ingest, not just the new rows.
- **`ai/`** — `llm.py:draft()` is the single masked entry point (see invariant #2). `providers.py` supports two adapters selected by `ai_format`: `openai` (OpenAI-compatible: OpenRouter default, also Ollama/OpenAI) and `anthropic` (Claude native). `config_store.py` reads live LLM config from the `app_settings` table (set via Admin UI) with fallback to `.env`, so the model can change **without rebuild/restart**. `narrative.py`/`summary.py` build payloads; `masking.py` does mask/unmask; `parsing.py` salvages fields from malformed/truncated LLM JSON (free models fence or truncate output) — route new LLM response parsing through it instead of bare `json.loads`.
- **`review.py`** — finding status transitions and revision history.
- **`reporting/`** — `report_data.py` gathers approved findings, then `docx_writer`/`html_writer`/`pdf_writer` (WeasyPrint renders Jinja2 HTML → PDF). `charts.py` renders severity/risk-matrix as inline SVG; `branding.py` pulls runtime letterhead from Admin settings. Attachments embed as data-URIs.
- **`eval/`** — deterministic value metrics (dedup efficiency, AI draft coverage, review progress, edit ratio) per engagement; `run.py` is a CLI that exits non-zero below threshold so it can gate CI.
- **`api/routes/`** — `auth`, `users`, `engagements` (the big one, ~700 lines: uploads, findings, review, attachments, evaluation, `report.docx|html|pdf`), `stats`, `admin`. `AuditMiddleware` (`core/audit.py`) logs all mutations to `audit_logs`. RBAC is fail-closed: **analyst** may edit/submit findings; only **auditor/admin** may approve/reject/mark false-positive; LLM config + audit trail are **admin**-only.
- **`ingest/watcher.py` + `scan_inbox` task (R3 auto-ingest)** — Celery **beat** scans `<watch_dir>/inbox/<engagement_id>/` (~every 30s, mounted from `datasets/watch/`) and auto-ingests settled files through the **same pipeline** as manual upload (`tool="unknown"` → sniff, `uploaded_by=None`), then moves them to `processed/` or `failed/`. Enabled by `watch_enabled`.

Models (`models/`): `Engagement`, `Finding` + `FindingRevision` (revision history distinguishes AI-draft vs auditor edits; AI-authored revisions have `author_id=None`), `ScanUpload`, `User`, `AppSetting`, `AuditLog`. Finding status flow: `draft → in_review → {approved | rejected | false_positive}`, any status reopen-able to `in_review`. Only `approved` reaches reports.

Raw uploads and evidence live in **MinIO**, not the DB (`core/storage.py`, keys like `uploads/<engagement_id>/...`).

### Frontend (`frontend/src/`) — Next.js 14 App Router + TypeScript

Deliberately dependency-light: `next`, `react`, and Phosphor icons only — no UI kit, no state library, no CSS framework. Styling is hand-written in a single `app/globals.css` (~540 lines of design tokens + component classes); reuse those classes rather than adding a styling dependency.

The working application is essentially two pages:

- **`app/engagements/[id]/page.tsx` (~1200 lines)** — the whole workflow, as three tabs: **files** (upload + parse status), **findings** (table/kanban, triage, AI narratives, review panel, attachments, history), **summary** (exec summary, eval metrics, report preview/download). Almost any feature request about the user-facing flow lands here.
- **`app/admin/page.tsx`** — LLM config, report branding, masking preview, audit trail.

`app/findings/page.tsx` and `app/reports/page.tsx` are **placeholder stubs** ("coming soon"), not implementations — check before assuming a feature has a home there. `lib/api.ts` is the single typed API client (calls `/api/*`, proxied same-origin), `lib/auth.tsx` handles JWT auth, `i18n/messages.ts` holds every ID/EN string — **add both locales when adding UI text**.

UI must follow the **Suryasoft UI/UX Blueprint**: navy chrome, no-flash dark mode, status shown as color + icon + text; fonts Space Grotesk + JetBrains Mono; Phosphor icons.

## Docs

`FLOW.md` is the authoritative step-by-step workflow, written for end users in Indonesian and keyed to the actual UI tabs ("Buka: tab **Temuan**") — read it when touching the user-facing flow, and update it when a step's location changes. `README.md` (also Indonesian) has the run/config/security details. The design specs `DPPL_AuditForge.tex` / `DUPL_AuditForge.tex` are referenced by the `D#`/`R#` tags in the code but are **not checked into this repo** — ask the user for them if you need the requirement text.
