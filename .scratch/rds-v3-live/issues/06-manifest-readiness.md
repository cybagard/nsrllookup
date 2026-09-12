# 06: Provisioning manifest, readiness gate, and per-result `dbhash`

**What to build:** the **Provisioning manifest** (a small record in the writable data dir:
**Set** + **Release** + ordered **Delta releases** + the three integrity values) becomes
the **readiness gate** — the container reads it at startup and reports `ready` **iff the
manifest is present AND its integrity values match the mounted db**. The **Sidecar index**
stores the **dbhash + Release** it was built from and **refuses to serve on mismatch**
(rebuild only on **Delta** apply). Each **Lookup Result**'s `dataset` block gains the
**final `dbhash`**; `/health` surfaces the verified **Release** + deltas + `dbhash`.
Respects **ADR-0005** (manifest = integrity token / readiness gate).

**Blocked by:** 05 (Provisioner writes the manifest)

**Status:** resolved

- [x] At startup the service reports `ready` **only when** the **Provisioning manifest** is
        present and its integrity values match the mounted db; absent/mismatch ⇒ `not-ready`.
- [x] The **Sidecar index** carries the **dbhash + Release** it was built from and refuses
        to serve if they no longer match the mounted db (rebuild only on **Delta** apply).
- [x] Each **Lookup Result**'s `dataset` block carries `set`, `release`, ordered `deltas`,
        and the **final `dbhash`**; the full triple + ordered per-delta chain live in the
        manifest / `/health`, not per result.
- [x] Smoke: manifest present ⇒ `ready` + a `known` answer carrying `dbhash`; manifest
        absent or mismatch ⇒ `not-ready` / refuses-serve.

## Answer

The readiness gate (ADR-0005) is now the single trust check at boot. `app.configure`
takes the loaded **Hash Set** *and* its **Provisioning manifest**; a private
`_ready()` defers to `hasheset.verify_readiness(manifest, hash_set)`, which is true
only when the manifest is present **and** its recorded identity (`set`, `release`,
ordered `deltas`, final `dbhash`) equals the Hash Set's provenance `dataset()`.
`/health` reports `ready` iff the gate passes; `/check` refuses to serve (503, still
audited, ADR-0004) when it does not — so a missing or mismatched manifest means the
mount answers nothing.

Three supporting changes made the gate coherent:

- **`hasheset.apply_delta` carries `dbhash` forward** — a freshly-applied Delta
   rebuilds the Sidecar index from the new `dbhash`-bearing db; previously it was
   dropped, so a delta-applied set could never agree with its manifest.
- **`Provision` finalises the returned set with the verified `dbhash`** — the
   orchestrator verifies layer 3 against NIST's `dbhashes.txt`, records that token
   (computed once, ADR-0006) into both the returned set's provenance and the
   manifest it writes, so the gate passes on a correctly-provisioned set.
- **`Provenance.dataset()` gains `dbhash`** — each **Lookup Result** and `/health`
   now surface the final token, the minimal field a forensic consumer needs to
   re-verify against `dbhashes.txt`; the full triple and ordered per-delta chain
   stay in the manifest.

New smoke `tests/integration/test_readiness.py` exercises the ticket's last
checkbox at Seam 1: a matching manifest ⇒ `ready` + a `known` answer carrying
`dbhash`; absent or mismatched ⇒ `not-ready` and `/check` 503. A consistency test
in `test_provision.py` asserts the manifest a provisioner writes matches the set it
returns (`verify_readiness` holds). Existing Seam-1/Seam-2 tests were updated for
the `dbhash` field and, where they drive HTTP, given a matching manifest. Suite:
**58 passed, 99% coverage**; `pyflakes` clean on all touched files.
