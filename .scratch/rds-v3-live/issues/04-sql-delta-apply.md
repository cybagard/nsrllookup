# 04: Apply a Delta release as real `.sql`, rebuild the index

**What to build:** a **Delta release** is NIST's `.sql` file of `INSERT/UPDATE/DELETE`
applied to the base **Hash Set** via SQLite execute-script (the `.read` mechanism, no
external CLI), which then **rebuilds the Sidecar index** and **refreshes Provenance** (the
**Release** + the now-applied, ordered **Delta releases**). Replaces the current row-dict
`apply_delta` with the real delta representation; fixtures model a **Delta** as inserts.

**Blocked by:** 03 (re-based data layer)

**Status:** ready-for-agent

- [ ] A **Delta** `.sql` is applied to the base db via SQLite execute-script, with no
        external CLI dependency.
- [ ] Applying a **Delta** rebuilds the **Sidecar index** and refreshes **Provenance**
        (release + ordered deltas).
- [ ] Smoke: a (small) **Delta** applied to a real-layout db updates the index, leaves the
        base unchanged, and refreshes provenance (extending the delta smoke).
- [ ] **Minimal** deltas apply only to **Minimal** bases (no cross-set application).
