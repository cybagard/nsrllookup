# 02: Migrate test suite to modern runner

**What to build:** the existing test suite runs on the modern test runner (+ a coverage
plugin), so all downstream slices can add tests in that runner. Live-server integration
tests are gated behind a flag so the suite is green without a running **Hash Set**.

**Blocked by:** 01 (Modern stack & runtime)

**Status:** ready-for-agent

- [ ] Existing unit behaviour is exercised on the modern runner and passes.
- [ ] Coverage is produced by the modern plugin, replacing the legacy coverage tool.
- [ ] Tests that require a live **nsrlsvr**/**Hash Set** are gated behind an explicit flag
      (or a fixture) and off by default, so `pytest` is green with no live server.
- [ ] The legacy test runner and its plugin no longer appear in the build or CI.

## Comments
