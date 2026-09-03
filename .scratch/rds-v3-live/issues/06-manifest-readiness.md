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

**Status:** ready-for-agent

- [ ] At startup the service reports `ready` **only when** the **Provisioning manifest** is
        present and its integrity values match the mounted db; absent/mismatch ⇒ `not-ready`.
- [ ] The **Sidecar index** carries the **dbhash + Release** it was built from and refuses
        to serve if they no longer match the mounted db (rebuild only on **Delta** apply).
- [ ] Each **Lookup Result**'s `dataset` block carries `set`, `release`, ordered `deltas`,
        and the **final `dbhash`**; the full triple + ordered per-delta chain live in the
        manifest / `/health`, not per result.
- [ ] Smoke: manifest present ⇒ `ready` + a `known` answer carrying `dbhash`; manifest
        absent or mismatch ⇒ `not-ready` / refuses-serve.
