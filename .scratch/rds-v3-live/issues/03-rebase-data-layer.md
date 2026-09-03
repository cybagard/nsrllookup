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

**Status:** ready-for-agent

- [ ] The data layer is re-based to `FILE`/`DISTINCT_HASH`; the synthetic
        `METADATA`/`md5sha1`/`filename` shape is gone.
- [ ] The **Sidecar index** is built by materialising `DISTINCT_HASH` (~72M distinct
        digests), not by a raw ~432M-row `FILE` scan.
- [ ] Membership is **case-agnostic**: a digest in any case resolves, normalised to
        UPPERCASE on both the index build and the input.
- [ ] `crc32` is physically present but rejected as a lookup **Algorithm**
        (MD5/SHA-1/SHA-256 only).
- [ ] Smoke: a **real-layout fixture Hash Set** answers known/unknown/invalid for MD5,
        SHA-1, SHA-256 (the data-layer smoke re-pointed at the real shape).
