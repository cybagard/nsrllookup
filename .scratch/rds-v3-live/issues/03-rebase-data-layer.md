# 03: Re-base the data layer onto the real `FILE`/`DISTINCT_HASH` layout

**What to build:** the data layer reads NIST's **real** layout instead of the synthetic
`METADATA(crc32, md5, md5sha1, sha1, sha256)` shape — a single red→green batch that
re-words the data layer and **every fixture together** (the "make the easy change" step
after 02 made the model explicit). It re-implements the **Set schema** term (`FILE` table +
`DISTINCT_HASH` view, per ADR-0001's no-standalone-index rationale). The **Sidecar index**
(per-Algorithm `hash→known`
index) is built by **materialising the `DISTINCT_HASH` view** (~72M distinct digests),
UPPERCASED, so membership is **case-agnostic**; `crc32` stays physically present but is
**not** a supported lookup **Algorithm**. Fixtures that used the synthetic
`crc32`/`md5sha1`/`filename` columns are rebuilt in the real shape.

**Blocked by:** 02 (domain model + ADRs) — this is the first implementation ticket that
must respect the recorded model.

**Status:** resolved

- [x] The data layer is re-based to `FILE`/`DISTINCT_HASH`; the synthetic
          `METADATA`/`md5sha1`/`filename` shape is gone.
- [x] The **Sidecar index** is built by materialising `DISTINCT_HASH` (~72M distinct
        digests), not by a raw ~432M-row `FILE` scan.
- [x] Membership is **case-agnostic**: a digest in any case resolves, normalised to
        UPPERCASE on both the index build and the input.
- [x] `crc32` is physically present but rejected as a lookup **Algorithm**
          (MD5/SHA-1/SHA-256 only).
- [x] Smoke: a **real-layout fixture Hash Set** answers known/unknown/invalid for MD5,
        SHA-1, SHA-256 (the data-layer smoke re-pointed at the real shape).

## Answer

Single red→green batch through `api/hasheset.py` and every fixture. `TABLE` is now
`FILE` with the real columns `(sha256, sha1, md5, crc32, file_name, file_size,
package_id)` and a `DISTINCT_HASH(sha256, sha1, md5, crc32)` view; the synthetic
`METADATA`/`md5sha1`/`filename` shape is gone. The **Sidecar index** materialises the
`DISTINCT_HASH` view (UPPERCASED) instead of scanning raw `FILE` rows, and `is_known`
UPPERCASES the input so membership is case-agnostic. `crc32` stays a column but is not a
lookup Algorithm. Every fixture was re-posed to the real shape (`file_name`/`file_size`/
`package_id`, no `md5sha1`); the data-layer smoke
(`api/tests/test_hasheset_layout.py`) now asserts the `FILE` table shape, the
`DISTINCT_HASH` view, UPPERCASE storage, no standalone index, and case-agnostic
membership.

Verification (in-container, == the CI `test` job): **40 passed, 0 skipped, 98%
coverage**; pylint 8.97/10 with the sole E-finding the pre-existing `E0015`
`pylintrc` quirk (no new E-findings; the `hasheset.py` per-file score is unchanged at
9.26). `apply_delta`'s `.sql` shape and the `dbhash`/manifest are left for tickets 04 and
06; the row-dict delta mechanism is retained here with a note, and stays green.
