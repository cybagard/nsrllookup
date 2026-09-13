# 03: Turnkey make provision / make verify driver

**What to build:** a **`Makefile`** exposing **`make provision`** and **`make verify`** plus
the thin orchestration that ties the **Provisioner** together end to end — the slice that
delivers "one command brings a fresh box to a verified **`ready`** state". `make provision`
owns: **verify** all three integrity layers (reusing the layer-1/2 verifiers and ticket 01's
layer-3 record-and-attest), **apply** the **Delta releases in order** onto the full
**Release** (via the existing `executescript` apply, rebuilding the **Sidecar index**),
**record** NIST's published token, and **write** the queryable **Hash Set** + **Sidecar
index** + **Provisioning manifest** into the data dir. `make verify` re-runs the layer checks
plus the manifest/readiness check against an already-provisioned volume. A layer failure
**refuses** the manifest write (ADR-0005: an unverified or partially-applied **Hash Set** can
never be served). The **API boundary (Seam 1)** and the **lookup module (Seam 2)** are
untouched. This slice uses the fetch from ticket 02 and the layer-3 record from ticket 01. No
new dependency.

**Blocked by:** 01 (Layer 3 records NIST's published dbhash), 02 (Fetch the Release and Delta
releases from NIST)

**Status:** resolved

- [x] `make provision` fetches (ticket 02), verifies all three layers, applies the **Delta
        releases in order**, records the published token (ticket 01), and writes the **Hash
       Set** + **Sidecar index** + **Provisioning manifest** into the data dir.
- [x] `make verify` re-checks an already-provisioned volume (layers hold + manifest present
        and well-formed) and reports the result.
- [x] Any integrity-layer failure **refuses** the manifest write (no unverified volume is
        produced).
- [x] Applying a **Delta release** already recorded in provenance is a no-op for the ordered
        list (no duplicate deltas on a re-run).
- [x] A fixture test (fetch stubbed) proves apply-in-order, manifest round-trip through
         `read_manifest`, and the refuse-on-mismatch branch.
- [x] The existing suite stays green; pylint on the new driver is clean.
