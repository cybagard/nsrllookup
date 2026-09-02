# 01: Modern stack & runtime

**What to build:** nsrllookup runs on a current, supported language runtime with a modern
WSGI server and current dependencies, and the service still answers its existing behaviour.
This is the prefactor that makes every later slice's tests runnable ("make the change easy,
then make the easy change").

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The service boots and serves on a current runtime (not an end-of-life one) with a
      current WSGI server.
- [x] Dependencies are on current, non-abandoned major versions; the legacy/abandoned test
      runner and its coverage plugin are removed.
- [x] The obsolete top-level compose `version` field is dropped and base images are tagged
      by minor version, not an EOL tag.
- [x] Existing behaviour is preserved (the current health/liveness route still responds).
- [x] No runtime, server, or dependency in the build is end-of-life or abandoned.

## Resolution

Committed at `74cf77d` ("Migrate to modern stack, pytest+coverage, and a CI test job",
tickets 01-03). Runtime moved python:3.9 -> 3.14-alpine (WSGI: waitress 3); deps onto
current majors (Flask 3.1, pytest 8, pytest-cov 5, coverage 7); legacy nose/Paste/
TransLogger + legacy coverage removed; top-level compose `version` dropped; health/
liveness route (`/health` + `/ping`) preserved. Verified: suite green, 38 passed, 98%.

## Comments
