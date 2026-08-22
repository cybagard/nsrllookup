# 06: `look_up` lookup module + full provenance for MD5

**What to build:** the new seam (Seam 2). A lookup module exposing one public function of
the form `look_up(hash_set, digests, algorithm) -> [Lookup Result]` that returns **Lookup
Results** with **Known/Unknown/Invalid** status and **full provenance** (the **Set**, the
**Release** date-version, and the applied **Delta releases**), tested at the lookup seam on
the fixture. Scope: **MD5**. This is the highest point at which data-driven lookup behaviour
is assertable without standing up HTTP over multi-gigabyte data.

The authoritative **Lookup Result** shape lives in `.scratch/rds-v3-migration/spec.md`
(Implementation Decisions → API contract); this ticket builds to that schema. Do not
re-paste the schema here — follow the spec.

**Blocked by:** 05 (Provision fixture Minimal Set + index), 02 (Migrate test suite to modern runner)

**Status:** ready-for-agent

- [ ] `look_up(hash_set, digests, algorithm)` returns one **Lookup Result** per digest.
- [ ] Each result carries **Known/Unknown/Invalid** status for its **Algorithm**.
- [ ] Each result carries the **Set**, **Release**, and applied **Delta releases** that
      answered (provenance).
- [ ] **Unknown** (checked, absent) is distinct from **Invalid** (never well-formed for the
      declared **Algorithm**).
- [ ] Tests assert this behaviour at the lookup seam on the fixture **Hash Set**; the module
      internal SQL is not tested.

## Comments
