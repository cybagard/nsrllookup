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
          `dbhash`, exercising all three layers end to end. **Capped path validated** (see
        `## OOM status`): `proof_bounded.py` runs layers 1–3 + turnkey apply + boot on real
        NIST artifacts (capped to keep the ~18 GiB base off a tight disk). The **uncapped**
        full-driver proof (`realdata_turnkey_proof.py`) is **not yet green — fetch plumbing
        gap**: its `local_opener` maps no top-level `signatures.txt`, so the real
        `driver.provision_release` refuses at the fetch stage (`FetchError: no local
        artifact for signatures.txt`). Close by mapping `signatures.txt` (or dropping it from
        the per-release fetch plan) before claiming this AC.
- [x] The **`dbhash`** recorded in the **Provisioning manifest** is NIST's real published
        token from that release's `dbhashes.txt` (not a stand-in). **VALIDATED** —
        `481e5f55f6d1ed63ea0f176779efc5cc5d53e52a`, read from the real
        `dbhashes.2026.09.1.txt` via `provision.read_published_dbhash`, recorded in the
        manifest (`proof_bounded.py`: "layer 3: real NIST dbhash read from dbhashes.txt"
        PASS; "manifest records real token + ordered deltas" PASS).
- [x] A service booted against the resulting volume reports **`ready`** and an answer carries
        the real token in its **Lookup Result** `dataset` block. **VALIDATED** —
        `proof_bounded.py` boots the provisioned volume: "/health reports ready" PASS;
        "/check: KNOWN/UNKNOWN answer carries real token" both PASS (token `481e5f55…` rides
        on the `dataset` block).
- [x] The run is recorded out-of-CI (not added to the automated suite); the full ~18 GiB
        download and prod host remain operator steps. **TRUE** — the proofs live under
        `.scratch/rds-v3-live/artifacts/` and stream the operator-fetched `raw/` set; the
        full ~18 GiB extract + 432 M-row apply stays an operator step (ADR-0003).

## OOM status (validated this session, 2026-09-15)

`notes.md`'s "Open item: the in-RAM index still OOMs on real data" is **addressed in the
working tree but UNCOMMITTED** — the OOM fixes are present in the uncommitted working tree,
not in HEAD (`3556c3e`, ticket 03). Validation on the working-tree code:

- **Index materialization OOM — RESOLVED (working tree).** `HashSet.__init__` no longer
  materialises an in-RAM `Set[str]` per Algorithm (~430 M each → tens of GB); membership is
  an in-DB B-tree `CREATE INDEX` (`idx_md5`/`idx_sha1`/`idx_sha256`) and a lookup is an
  indexed on-disk seek. `ram_sized_index_proof.py` (in-DB index, no in-RAM materialisation):
  peak RSS **flat ~0.1–2.8 MiB** across 50 K / 500 K / 5 M rows while the on-disk index
  grows 8 → 80 → 800 KiB. The OOM (RSS scaling with the distinct-digest count) is gone.
- **Delta-apply OOM / disk blowup — RESOLVED (working tree).** `apply_delta` no longer feeds
  the whole Delta `.sql` (~1 GB / 3.8 M `INSERT`s) to `executescript` (the "query string is
  too large" failure); it streams + batches via `_apply_sql_stream`. `proof_bounded.py`
  applies the real Deltas streamed+batched (100 K rows / 0.8 s, capped) with no OOM and no
  169 GB base. (Process peak ~1.4 GiB is the real-Delta-file working set, bounded by file
  size, not the ~430 M×3 distinct-digest count — the OOM that crashed the old design.)
- **Caveat — fix is uncommitted.** HEAD still materialises the in-RAM set; commit the
  working-tree `hasheset.py` (and the boot/`verify` read-the-mount changes) before this is
  durable. See `git status` — `api/hasheset.py`, `api/boot.py`, `api/driver.py` are modified
  but uncommitted.
