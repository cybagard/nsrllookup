# 03: CI test job

**What to build:** a CI job runs the modern test suite green on every push. The existing
workflow set is static scans only, so a behavioural test job is first-class new.

**Blocked by:** 02 (Migrate test suite to modern runner)

**Status:** resolved

- [x] A CI job runs the unit + integration suites and reports a pass/fail.
- [x] The job is green for the default (no-live-server) configuration.
- [x] The job surfaces coverage.
- [x] Lint/scan jobs that already exist are not regressed.

## Resolution

Committed at `74cf77d` (with 01, 02). Added `.github/workflows/test.yml`: runs the
suite on Python 3.14, green on the no-live default (`live` marker off), surfaces
coverage via `--cov-report=xml`/`term-missing`; pre-existing scan jobs
(anchore-analysis, codacy-analysis, codeql-analysis) left untouched.

## Comments
