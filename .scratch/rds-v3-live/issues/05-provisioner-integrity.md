# 05: Turnkey Provisioner with three-layer integrity verification

**What to build:** the **Provisioner** — a one-time, out-of-band, operator-run flow
(wizard-driven; `make provision` / `make verify`) that **fetches** a **Release** + its
**Delta releases**, **verifies integrity in three layers**, **applies** the deltas in
order, and **writes** the queryable **Hash Set** + **Sidecar index** + **Provisioning
manifest**. Never a build or CI step; the container stays a pure read-only consumer.
Respects **ADR-0006** (accepting NIST's external `dbhash`).

**Blocked by:** 04 (real delta apply)

**Status:** ready-for-agent

- [ ] The Provisioner fetches a **Release** + **Delta releases** from NIST's distribution.
- [ ] **Layer 1:** each zip's **SHA-1** matches its `.sha` sidecar.
- [ ] **Layer 2:** the inner **SHA-256** values from `signatures.txt` match the shipped
        delta/schema component files.
- [ ] **Layer 3:** NIST's **`dbhash`** (external binary) over the **final post-delta** db
        matches the value published in `dbhashes.txt`; that value is the integrity token
        recorded for the **Release**.
- [ ] The Provisioner applies deltas in order and writes the **Hash Set** + **Sidecar
        index** + **Provisioning manifest**.
- [ ] Provisioning is a one-time, out-of-band step — not part of build or CI.
