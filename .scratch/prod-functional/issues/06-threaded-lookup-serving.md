# 06: Serve Lookup Sessions from the request's thread (the waitress serving path)

**What to build:** the deployed service must answer `POST /check` when the request
arrives on a **waitress worker thread**, not just on the thread that booted the
service.

**The defect (discovered in a post-04 live smoke, 2026-09-28):** the production
launch (`docker-compose.prod.yml` `command: python /api/app.py`) serves requests
on waitress's worker threads, but the **Hash Set**'s single read-only connection
is opened once at boot on the main thread. CPython's `sqlite3` keeps connections
thread-affine by default (`check_same_thread=True`), so the very first
`POST /check` on a worker thread raises
`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in
that same thread` — an unhandled **500** on *every* Lookup Session, and no
**Audit Entry** is ever recorded. The suite is green only because every test
serves through the single-threaded Flask test client; no test exercises a
request on a different thread than the one that loaded the mount.

**The fix stays at the data layer, inside `HashSet` (Seam 2's object, the seams
themselves are untouched — Seam 1 and Seam 3 are not modified):** CPython's
`sqlite3` guarantees a connection may *cross* threads with
`check_same_thread=False` but does **not** guarantee *concurrent* use of the
same connection, so the single shared read-only connection (ADR-0001: no
in-RAM digest copy, bounded handles) must be synchronized on the application
side — a lock held across the indexed membership query. The read-only load
(ADR-0006: trust the verified mount; never a writable path or a boot-time index
rebuild) and the lookup contract, **Lookup Result** shape, and Audit Trail are
unchanged.

**Blocked by:** none (prod-functional 01–05 are resolved; this was found by
running the provisioned service live after ticket 04).

**Status:** resolved

- [x] A Lookup Session answered **from a worker thread** (the deployed serving
      shape: connection opened at boot, `look_up` called from another thread)
      returns one correct **Lookup Result** per Digest with the right
      `Known`/`Unknown`/`Invalid` status and full provenance. The test goes red
      with `ProgrammingError` before the fix.
- [x] **Concurrent** Lookup Sessions against one provisioned **Hash Set**
      (several worker threads simultaneously) all return correct results — the
      single shared connection is application-synchronized.
- [x] The invariant of the mount is preserved: the fix adds no writable path,
      no per-boot index rebuild, and the ADR-0006 read-only connect remains the
      one and only boot load.
- [x] Full suite green in the dev container + pylint clean on the changed
      module; and a live `waitress` smoke: `python /api/app.py` against a
      provisioned volume answers `/health` ready and a real `POST /check` with
      HTTP 200 and correct results.

## Comments

- 2026-09-28: Implemented TDD. Red: `api/tests/integration/test_threaded_lookup.py`
  (worker-thread lookup + 8-way concurrent sessions) failed with the exact
  `sqlite3.ProgrammingError` from production. Green: `HashSet` in
  `api/hasheset.py` opened with `check_same_thread=False` and each membership
  query holds a `threading.Lock`. Full suite in the dev container: 106 passed,
  1 skipped (env: read-only dir as root), 95% coverage; pylint on the changed
  module at baseline (two pre-existing conventions in the delta scanner, not
  from this change). Live smoke: `python /api/app.py` against a provisioned
  volume → `/health` ready, `POST /check` HTTP 200 with
  known/unknown/invalid results + full provenance, Audit Entry recorded.
- 2026-09-28 (code review): two-axis review of the landing diff found the
  worker-thread test was actually running the session on the test's own thread
  (so it could never be the red) and the spec note was spliced mid-sentence.
  Both fixed: the worker test now answers from a real worker thread (verified
  red pre-fix), and the spec note is a standalone item. Second commit.
