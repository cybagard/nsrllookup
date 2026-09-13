# 04: Real-data proof of the turnkey path (out of CI)

**What to build:** the turnkey path is proved *for real* by actually running the driver /
**`make provision`** on a real NIST Minimal **Release** that **publishes** a **`dbhash`**
token, out-of-CI, and recording the result — so layer 3 is NIST's *real published* token, not
a stand-in. This closes the one open strand `rds-v3-live` ticket 07(b) left: its curated
`RDS_2021.12.2` release predates the `dbhashes.txt` convention, so a real token could not be
checked there. A current **Release** (e.g. a 2026.x Minimal release that ships
`dbhashes.txt` with a value such as `481e5f55…`) is used so the recorded token is genuinely
NIST's. This proof is **not** added to the automated suite (real-data I/O is multi-GB and must
never block a PR, per the `rds-v3-live` Testing Decisions); it is run and recorded. The full
~18 GiB Minimal download and the production host stay **operator steps**.

**Blocked by:** 03 (Turnkey make provision / make verify driver)

**Status:** ready-for-agent

- [ ] The driver / `make provision` runs on a real NIST Minimal **Release** that publishes a
        `dbhash`, exercising all three layers end to end.
- [ ] The **`dbhash`** recorded in the **Provisioning manifest** is NIST's real published
        token from that release's `dbhashes.txt` (not a stand-in).
- [ ] A service booted against the resulting volume reports **`ready`** and an answer carries
        the real token in its **Lookup Result** `dataset` block.
- [ ] The run is recorded out-of-CI (not added to the automated suite); the full ~18 GiB
        download and prod host remain operator steps.
