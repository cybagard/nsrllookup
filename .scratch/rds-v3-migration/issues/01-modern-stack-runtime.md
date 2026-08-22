# 01: Modern stack & runtime

**What to build:** nsrllookup runs on a current, supported language runtime with a modern
WSGI server and current dependencies, and the service still answers its existing behaviour.
This is the prefactor that makes every later slice's tests runnable ("make the change easy,
then make the easy change").

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The service boots and serves on a current runtime (not an end-of-life one) with a
      current WSGI server.
- [ ] Dependencies are on current, non-abandoned major versions; the legacy/abandoned test
      runner and its coverage plugin are removed.
- [ ] The obsolete top-level compose `version` field is dropped and base images are tagged
      by minor version, not an EOL tag.
- [ ] Existing behaviour is preserved (the current health/liveness route still responds).
- [ ] No runtime, server, or dependency in the build is end-of-life or abandoned.

## Comments
