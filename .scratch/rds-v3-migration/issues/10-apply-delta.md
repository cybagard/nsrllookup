# 10: Apply a Delta release at ingest

**What to build:** the new "stay current" mechanism. Provisioning applies a **Delta release**
onto the current full **Release**, producing an updated **Hash Set**. NIST publishes a full
**Release** quarterly in March and **Delta releases** in June/September/December; this is
the step that layers a **Delta** on without a full re-provision.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** resolved

- [x] A **Delta release** is applied onto the current full **Release**, yielding an
      updated current dataset.
- [x] Provisioning identifies the current **Release** and the **Delta release(s)** applied,
      and records that provenance for the **Hash Set**.
- [x] Provisioning is a one-time mount/ingest step, not a build or CI step.
- [x] A smoke check confirms applying a (small sample) **Delta** to a minimal-style DB yields
      a valid updated **Hash Set**.

## Comments

`api/hasheset.py` gains `apply_delta(base, delta_rows, delta_release)`: it copies the
base **Set** rows (`_copy_rows`), merges the delta's rows into a fresh sqlite db,
rebuilds the per-Algorithm index via the existing `HashSet.__init__`, and appends the
delta to the **Provenance**. It is a one-time ingest step (tempfile-backed, no request-
path involvement). Smoke check `api/tests/test_apply_delta.py` proves the delta adds rows,
the index reflects them, the base is unchanged, and provenance is refreshed.
