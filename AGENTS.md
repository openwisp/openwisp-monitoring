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

## Contributing Guidelines

- Before editing, inspect the relevant implementation, tests, documentation, and configuration. Follow existing repository patterns and do not invent behavior or requirements.
- Keep each contribution focused and change only the lines necessary for its goal. Do not include unrelated refactors, formatting churn, or generated and dependency-file changes unless explicitly required.
- Add or update focused tests for every behavior change. Use test-driven development when the scope is very clear, such as bug fixes or narrowly scoped changes. For new features, tests may be added after implementation, but confirm they fail when key feature code is removed. When a test failure does not clearly state the expected outcome that was not met, add an explicit assertion message.
- Run `openwisp-qa-format` after each change when available.
- Run the relevant targeted tests, builds, and documented QA checks, including `./run-qa-checks` when provided. Do not claim a change is complete when verification fails; report the failure or blocker.
- When requirements, intended behavior, or an unexpected failure are unclear, stop and seek clarification instead of making speculative changes.
- When starting work on a new issue, create a new branch from `master`. Use `issues/<issue-number>-<short-title>` for issue work; otherwise, use a short, descriptive branch name.
- Commit messages must be descriptive and use past tense. Past tense is a writing guideline that agents and contributors must follow; it is not checked automatically. For issue work, use an allowed prefix and a capitalized, past-tense subject ending with `#<issue-number>`, for example `[fix] Fixed perennial "modified" state #213`. Repeat the issue reference in the body with `Fixes`, `Closes`, `Resolves`, or `Related to` as appropriate. Use `openwisp-commit --check` to validate the structural commit convention and `cz -n cz_openwisp info` to view the allowed prefixes and message structure.
- Add an explanatory commit body only for substantial changes, new features, or non-obvious bug fixes. The releaser automatically publishes the subject of `[feature]`, `[change]`, `[change!]`, `[deps]`, and `[fix]` commits, including scoped variants, in the changelog. Write those subjects in clear, user-friendly language suitable for release notes.
- Send new commits in response to review feedback instead of amending existing commits.

## Development Notes

- Preserve public APIs, migrations, swappable models, metric names, time series schemas, alert semantics, and integration points unless explicitly required.
- Mark user-facing strings for translation with Django i18n helpers in Django code.
- Place imports at the top of the file. Only defer imports when necessary (e.g., Django model imports inside functions or methods where the app registry is not yet ready).
- Avoid unnecessary blank lines inside function and method bodies.
- Prefer short, precise names that rely on their nearest meaningful scope. Do not repeat a feature, domain object, or namespace already named by the containing module, class, or function. For example, prefer `EstimatedLocation.refresh()` over `EstimatedLocation.refresh_estimated_location()`. Repeat that context only when the name is used outside that scope or is needed to distinguish genuinely different concepts. When a concise name cannot express a necessary distinction, use a concise docstring to describe it rather than encoding it in an excessively long name.
- Before adding a comment or docstring, ask whether it conveys information a reader cannot reasonably infer from clear code, names, and surrounding scope. Add a concise comment when it explains a non-obvious reason, constraint, compatibility or security requirement, side effect, or unavoidable complexity. In opaque syntax or domain-specific code, especially shell scripts, a comment may also explain what the code does. Do not add comments that merely restate adjacent code one-to-one.
- Update docs when behavior, settings, public APIs, setup steps, metrics, or supported versions change, including when a documented feature's behavior changes or a new user-facing feature is added.

## Testing and QA

- Prefer method decorators for context managers that apply to the entire test method and would otherwise create unnecessary nesting, unless decorator ordering conflicts or the context manager requires data unavailable when the method is defined.
- When separate tests cover different cases of the same feature, share almost identical database preparation, and primarily vary in input or expected outcome, group them in one test method with subTest. This is especially encouraged, but not limited to, TransactionTestCase tests, where it avoids repeated expensive database setup and teardown. Keep each subtest's setup explicit and independent, and retain separate test methods when cases exercise genuinely distinct behavior. Leave one blank line immediately before each with self.subTest(...): call.
- During development, run the focused tests and test suites directly affected by the change instead of routinely running the full test suite. For example, run the relevant `test_admin` tests for admin changes and Selenium tests for JavaScript or browser-facing changes.
- Changes to core logic, model validation, migrations, database schema, tenant isolation, authentication, or shared behavior require all affected package and integration suites.
- Before pushing a branch or opening a pull request for a behavior-affecting change, verify that the full test suite has passed at least once for the current branch after its latest code, test, dependency, migration, or configuration change. If no successful full-suite result is available, stop, report the missing verification, and do not push or open the pull request. If the full suite cannot run, report the blocker and wait for user direction.
- Prefer in-process tests so coverage tools can measure changed code.

## Django Notes

- Preserve tenant isolation and object-level permissions for organizations, devices, checks, metrics, charts, alerts, and related data.
- Be careful with queryset filtering, serializers, admin behavior, cache invalidation, signals, Celery tasks, time series database backends, and dashboard/websocket updates.
- When changing APIs, include tests for permissions, validation, filtering, pagination, and tenant boundaries.
- When a Celery task, notification, cache invalidation, or other external side effect depends on database changes made in the current transaction, register it with `transaction.on_commit()` so it cannot run against uncommitted or rolled-back data. Do not defer work that must run before commit or is independent of the transaction. Test commit and rollback behavior, and account for Celery eager execution in tests versus asynchronous execution in production.

## Security Notes

- Watch for cross-tenant data leaks, permission bypasses, unsafe query construction, excessive metric ingestion, insecure credentials, and secrets.
- Preserve validation around metric payloads, device data, alert configuration, time series queries, URLs, and backend credentials.

## Troubleshooting

- If documentation and CI commands differ, use CI for verification and report the exact documentation path, CI workflow path, and differing commands. Do not change the documentation until the user explicitly chooses one of these actions: update the named documentation file in the current change because the divergence was caused by that change, or leave it unchanged for a separate follow-up. Never decide that scope distinction independently.
