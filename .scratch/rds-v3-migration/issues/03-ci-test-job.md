# 03: CI test job

**What to build:** a CI job runs the modern test suite green on every push. The existing
workflow set is static scans only, so a behavioural test job is first-class new.

**Blocked by:** 02 (Migrate test suite to modern runner)

**Status:** ready-for-agent

- [ ] A CI job runs the unit + integration suites and reports a pass/fail.
- [ ] The job is green for the default (no-live-server) configuration.
- [ ] The job surfaces coverage.
- [ ] Lint/scan jobs that already exist are not regressed.

## Comments
