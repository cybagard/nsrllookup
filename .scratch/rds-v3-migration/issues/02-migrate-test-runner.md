# 02: Migrate test suite to modern runner

**What to build:** the existing test suite runs on the modern test runner (+ a coverage
plugin), so all downstream slices can add tests in that runner. Live-server integration
tests are gated behind a flag so the suite is green without a running **Hash Set**.

**Blocked by:** 01 (Modern stack & runtime)

**Status:** resolved

- [x] Existing unit behaviour is exercised on the modern runner and passes.
- [x] Coverage is produced by the modern plugin, replacing the legacy coverage tool.
- [x] Tests that require a live **nsrlsvr**/**Hash Set** are gated behind an explicit flag
       (or a fixture) and off by default, so `pytest` is green with no live server.
- [x] The legacy test runner and its plugin no longer appear in the build or CI.

## Resolution

Committed at `74cf77d` (with 01, 03). Added `api/pytest.ini` + `api/conftest.py`;
live-server tests gated behind the `live` marker / `--live` / `NSRLLOOKUP_LIVE`, off by
default, so bare `pytest` is green with no Hash Set; nosetests/Paste/TransLogger removed
from the build and CI. Verified: 38 passed, 0 skipped, 98% coverage.

## Comments
