# AGENTS.md

## Project Overview

`openwisp-monitoring` is the OpenWISP Django app for collecting device metrics, running checks, storing time series data, rendering charts, and generating alerts.

Core code lives in `openwisp_monitoring/`:

- `monitoring/` handles metrics, charts, alerts, thresholds, and time series integration.
- `check/` handles health checks and tolerance logic.
- `device/`, `db/`, `views.py`, `utils.py`, and `settings.py` provide device integration, database helpers, views, utilities, and settings.
- Tests live in `openwisp_monitoring/tests/` and `tests/`.

## Source of Truth

- Use `docs/developer/installation.rst` and `docs/developer/index.rst` for local setup, services, and baseline test commands.
- Use `.github/workflows/ci.yml` for CI-tested dependencies, QA/test commands, env vars, and supported Python/Django versions.
- Use GitHub issue/PR templates when asked to open issues or PRs.

Follow the DRY principle: do not duplicate information or code across files.

If instructions conflict, repository config and CI workflows win first, official docs next, and this file is supplemental.

## Development Notes

- Keep changes focused. Avoid unrelated refactors and formatting churn.
- Preserve public APIs, migrations, swappable models, metric names, time series schemas, alert semantics, and integration points unless explicitly required.
- Mark user-facing strings for translation with Django i18n helpers in Django code.
- Place imports at the top of the file. Only defer imports when necessary (e.g., Django model imports inside functions or methods where the app registry is not yet ready).
- Avoid unnecessary blank lines inside function and method bodies.
- Prefer patch decorators when a test patch spans the whole method, to avoid unnecessary nesting.
- Update docs when behavior, settings, public APIs, setup steps, metrics, or supported versions change.

## Testing and QA

- Add or update tests for every behavior change.
- For bug fixes, write the regression test first, run it against the unfixed code, confirm it fails for the expected reason, then implement the fix.
- Use targeted tests while iterating, then run the documented full test command before considering the change complete.
- Run `openwisp-qa-format` after editing when available.
- Run `./run-qa-checks` when present. Treat failures as blocking unless confirmed unrelated and reported.
- Prefer in-process tests so coverage tools can measure changed code.

## Django Notes

- Preserve tenant isolation and object-level permissions for organizations, devices, checks, metrics, charts, alerts, and related data.
- Be careful with queryset filtering, serializers, admin behavior, cache invalidation, signals, Celery tasks, time series database backends, and dashboard/websocket updates.
- When changing APIs, include tests for permissions, validation, filtering, pagination, and tenant boundaries.

## Security Notes

- Watch for cross-tenant data leaks, permission bypasses, unsafe query construction, excessive metric ingestion, insecure credentials, and secrets.
- Preserve validation around metric payloads, device data, alert configuration, time series queries, URLs, and backend credentials.
- Write comments and docstrings only when they explain why code is shaped a certain way. Put comments before the relevant code block instead of scattering them inside it.

## Troubleshooting

- If setup, QA, or tests fail, check docs first, then compare with CI. If commands diverge, follow CI.
