# 04: Apply a Delta release as real `.sql`, rebuild the index

**What to build:** a **Delta release** is NIST's `.sql` file of `INSERT/UPDATE/DELETE`
applied to the base **Hash Set** via SQLite execute-script (the `.read` mechanism, no
external CLI), which then **rebuilds the Sidecar index** and **refreshes Provenance** (the
**Release** + the now-applied, ordered **Delta releases**). Replaces the current row-dict
`apply_delta` with the real delta representation; fixtures model a **Delta** as inserts.

**Blocked by:** 03 (re-based data layer)

**Status:** resolved

- [x] A **Delta** `.sql` is applied to the base db via SQLite execute-script, with no
        external CLI dependency.
- [x] Applying a **Delta** rebuilds the **Sidecar index** and refreshes **Provenance**
         (release + ordered deltas).
- [x] Smoke: a (small) **Delta** applied to a real-layout db updates the index, leaves the
        base unchanged, and refreshes provenance (extending the delta smoke).
- [x] **Minimal** deltas apply only to **Minimal** bases (no cross-set application).

## Answer

Implemented at `131598e`. `apply_delta(base, delta_sql, delta_release, set_name=None)`
now runs NIST's ordered `.sql` against a **copy** of the base db via
`sqlite3.executescript` (the documented `.read` mechanism, no external CLI — no row-dict
merge, no `build_minimal_fixture_db` rebuild), then rebuilds the **Sidecar index** by
re-provisioning the copy and refreshes **Provenance** with the ordered, now-applied
**Delta** (deduped). A Delta is guarded against a base of a different **Set**: a `set_name`
that differs from the base's `set_name` is refused with `ValueError` — Minimal deltas apply
only to Minimal bases, no cross-set application.

`build_delta_sql(rows)` is the new fixture seam: it renders a Delta's `FILE` inserts as
NIST's `BEGIN TRANSACTION; INSERT INTO FILE (sha256, sha1, md5, crc32, file_name,
file_size, package_id) VALUES (...); COMMIT` shape (real Minimal columns, value case as
given, a `;` per statement to keep it `executescript`-safe). Fixtures model a Delta as a
set of insert rows through this, so the apply path is exercised by the real mechanism.

The module was modernised in the same batch: standard PEP-8 4-space indentation, f-strings,
a public `HashSet.path` accessor (clears the prior `W0212`), a `COLUMN_TYPES` map used to
build the fixture `FILE` DDL, and the old row-dict `apply_delta` + `_copy_rows` are gone.
`hasheset.py` is now **lint-clean**. The `dbhash`-over-final-db and the 3-layer integrity
are left for ticket 05; `Provenance.dataset()` still carries `set`/`release`/`deltas`
(`dbhash` is a ticket 06 addition).

Verification (in-container, == the CI `test` job): **42 passed, 0 skipped, 98% coverage**;
`pylint` on `hasheset.py` is **0 findings** (prior `W0212` + two `C0209` cleared; the
module `app.py` C/W findings and the `E0015` `pylintrc` quirk are pre-existing and
untouched). Added checks: `test_apply_delta_leaves_base_untouched` (copy-on-apply leaves
the base's rows/index unchanged) and `test_delta_refused_on_mismatched_set` (cross-set
refusal).
