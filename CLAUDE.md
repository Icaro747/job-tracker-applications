# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Django app for managing job applications: cataloging companies/jobs/applications, ingesting status-update emails from configured senders, classifying them, and (later) reducing repetitive form filling. The project is **pt-BR**: code comments, model `verbose_name`s, URL path segments, and all UI text are in Portuguese. Keep that convention when adding code.

## Commands

The project uses a **local virtualenv (`.venv`) + pip**, not uv. Always run Python through the venv interpreter.

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate

# Run
python manage.py runserver        # app at http://127.0.0.1:8000/ , admin at /admin/

# Tests (pytest-django; config in pytest.ini, uses --reuse-db)
.\.venv\Scripts\python.exe -m pytest                    # full suite
.\.venv\Scripts\python.exe -m pytest tests/email_ingestion/test_scan_pipeline.py   # one file
.\.venv\Scripts\python.exe -m pytest -k matches          # by name
.\.venv\Scripts\python.exe -m pytest --cov                # coverage (pytest-cov installed)

# Email scan pipeline (Fila 1) — manual trigger
python manage.py scan_emails

# After changing installed packages, regenerate the lockfile
python -m pip freeze > requirements.txt
```

Note: `.claude/settings.md` documents PostToolUse hooks that reference `uv run ...`. The canonical project workflow is **pip + `.venv`** (see `docs/tdd.md` and README) — prefer the venv commands above; uv is not the project's package manager.

## TDD is mandatory

This project develops strictly test-first (red → green → refactor); see `docs/tdd.md`. Write a failing test before production code. Tests live in the **top-level `tests/` package** mirroring app structure (`tests/applications/`, `tests/email_ingestion/`, etc.), **not** in each app's `tests.py` (those files are vestigial stubs). Shared `pytest` fixtures (`user`, `auth_client`) are in `tests/conftest.py`; Factory Boy factories for every model are in `tests/factories.py` (reuse them rather than building model instances inline).

## Architecture

Six Django apps under `config/` settings. Only **Etapas 1–3 are implemented**; later stages are scaffolded with placeholder models.

| App | Role | Status |
|---|---|---|
| `accounts` | Custom `User` (email-only auth via django-allauth) | Etapa 1 ✅ |
| `applications` | Companies, jobs, applications, timeline, audit | Etapas 1–2 ✅ |
| `email_ingestion` | Email accounts, provider adapters, scan rules, Fila 1 | Etapa 3 ✅ |
| `candidate_profile` | Résumé/profile data | model scaffolded |
| `notifications` | Reminders/calendar events | scaffolded (Etapa 5) |
| `autofill` | Form-fill suggestions | scaffolded (Etapa 6) |

Per-domain behavioral specs live in `.specs/` (00–11); `.specs/README.md` maps the build stages. Read the relevant spec before changing a domain — it defines intended behavior, not the code.

### Cross-cutting patterns (read these before editing)

- **Global vs. per-user resources.** `Company` and `Job` are *global, shared* — any authenticated user may create/edit/delete them. `JobApplication` and `CandidateProfile` are *private to a user*. Don't add per-user ownership filters to Company/Job views, and always scope application/profile queries to `request.user`.

- **Soft delete via custom managers.** `User`, `JobApplication`, and `CandidateProfile` use a "soft delete" `deleted_at` field. The default manager `objects` **hides** deleted rows (and rows belonging to deleted users); use `all_objects` to reach everything. `User.soft_delete(keep_global_data=...)` cascades the deletion choice (Opção A wipes personal data, Opção B keeps global Company/Job authorship). When querying these models, prefer `objects` unless you specifically need deleted records.

- **Fat models, thin views.** Domain transitions live on the model, not in views: `JobApplication.change_status()`, `set_next_action()`, `complete_next_action()`, and `add_note()` mutate state *and* append an `ApplicationTimelineEntry`. The timeline is append-only. Call these methods instead of setting fields directly so timeline/audit stay consistent.

- **Company audit log.** `CompanyAuditLog` records one row **per changed field** (not per operation) and exists only for `Company`. Views must call `CompanyAuditLog.record_create/record_update/record_delete` (capture old values before `save()` for updates). No other model has this.

- **Email provider adapters.** The pipeline never talks to Gmail/IMAP directly. `email_ingestion/adapters/base.py` defines the `EmailProviderAdapter` ABC and the normalized `FetchedMessage` dataclass; `get_adapter(account)` is a factory keyed on `account.provider`. Adding a provider = new subclass + registry entry in `adapters/__init__.py`, no pipeline changes. `services.scan_account()` (Fila 1) authenticates via the adapter, applies active `EmailSenderRule`s (`rule.matches()`), dedups by `message_id`, and creates pending `InboundEmail`s. `enqueue_classification()` is a deliberate no-op hook for Etapa 4 (LLM/Fila 2) — leave the integration point in place.

- **Settings & env.** `config/settings.py` loads `.env` with a hand-rolled `load_local_env()` (no python-dotenv) and never overrides real env vars. Google OAuth credentials (`GOOGLE_OAUTH_CLIENT_ID/SECRET`) serve double duty: allauth social login *and* Gmail connection. When unset, the app degrades gracefully (email/password login still works) — preserve that fallback.

- **URLs & views.** App URLConfs use namespaces (`app_name = 'applications'`, etc.) with Portuguese path segments; reference routes as `applications:application_detail`. Views are class-based generics (`LoginRequiredMixin` + `ListView`/`CreateView`/…) plus small `@login_required @require_POST` function views for HTMX actions on the application detail page (status change, add note, next action). The project uses HTMX for partial updates — see `.claude/skills/htmx-patterns`.

## Environment notes

- Windows / PowerShell is the primary shell; the README and docs use PowerShell syntax.
- Django 6.0, Python 3.12, SQLite in dev.
- A `PreToolUse` hook blocks file edits while on the `main` branch — work on a feature branch.
