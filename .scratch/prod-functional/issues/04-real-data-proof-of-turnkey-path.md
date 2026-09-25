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

**Status:** resolved

- [x] The driver / `make provision` runs on a real NIST Minimal **Release** that publishes a
          `dbhash`, exercising all three layers end to end. **Capped path validated** (see
        `## OOM status`): `proof_bounded.py` runs layers 1–3 + turnkey apply + boot on real
        NIST artifacts (capped to keep the ~18 GiB base off a tight disk). The **uncapped**
        full-driver proof (`realdata_turnkey_proof.py`) is **complete** (2026-09-24, 315.3
        min, ALL PASS): it ran the real driver on the real `RDS_2026.03.1` release + both real
        Deltas via the bounded algorithm of **ADR-0007** (in-place scratch apply, same-volume
        rename publish, resumable fetch) in the dev container — the failure mode that took the
        Docker VM's ext4 down (a 500–730 GiB peak on a small pool + 8 GiB VM) is designed
        out, not brute-forced, and the measured peak proved the bound (peak == final volume).
        The old "fetch plumbing gap" is closed by `5fecbbd`: NIST publishes **no**
        top-level `signatures.txt` (probes 403; each archive ships its inner one), so the
        fetch plan no longer looks for one. The measured footprint and AC outcomes are
        recorded under `## Uncapped turnkey run on a small machine (ADR-0007)`.
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

## Comments

### OOM status (validated this session, 2026-09-15)

`notes.md`'s "Open item: the in-RAM index still OOMs on real data" is **addressed and
committed on main** — the OOM fixes landed as `0af05af` (in-database hash index + streamed
delta apply + trust-the-mount), ahead of the ticket 03 driver (`3556c3e`). Validation runs
on that code:

- **Index materialization OOM — RESOLVED.** `HashSet.__init__` no longer
  materialises an in-RAM `Set[str]` per Algorithm (~430 M each → tens of GB); membership is
  an in-DB B-tree `CREATE INDEX` (`idx_md5`/`idx_sha1`/`idx_sha256`) and a lookup is an
  indexed on-disk seek. `ram_sized_index_proof.py` (in-DB index, no in-RAM materialisation):
  peak RSS **flat ~0.1–2.8 MiB** across 50 K / 500 K / 5 M rows while the on-disk index
  grows 8 → 80 → 800 KiB. The OOM (RSS scaling with the distinct-digest count) is gone.
- **Delta-apply OOM / disk blowup — RESOLVED.** `apply_delta` no longer feeds
  the whole Delta `.sql` (~1 GB / 3.8 M `INSERT`s) to `executescript` (the "query string is
  too large" failure); it streams + batches via `_apply_sql_stream`. `proof_bounded.py`
  applies the real Deltas streamed+batched (100 K rows / 0.8 s, capped) with no OOM and no
  169 GB base. (Process peak ~1.4 GiB is the real-Delta-file working set, bounded by file
  size, not the ~430 M×3 distinct-digest count — the OOM that crashed the old design.)
- **Committed — caveat resolved.** The fixes are on main (`0af05af`: `hasheset.py` in-DB
  index, `driver.py` streamed delta apply, `boot.py`/`verify` trust-the-mount); the
  uncommitted-working-tree caveat is obsolete.

### Uncapped turnkey run on a small machine (ADR-0007) — completed 2026-09-24

The uncapped proof does not brute-force the machine: **ADR-0007** bounds the run's
disk peak to ~260 GiB on one volume (the archive + one indexed database). The old
pipeline peaked at 500–730 GiB on a pool that could not hold it -- that over-run,
not the data, is what took the Docker VM's ext4 down with a write-EIO storm at
07:17Z on 2026-09-21. How the bound is achieved:

- **In-place Delta apply on scratch** -- `hasheset.apply_delta(..., in_place=True)`;
  the driver routes in-place only for the run's own working copy (copy-on-apply
  remains the protection for trusted mounted volumes, ADR-0005). No second full
  copy of the database ever exists.
- **Same-volume rename publish** -- the extracted base and the finished database
  move by `os.replace` (an O(1) rename); a streamed copy only across volumes. No
  third full copy.
- **Resumable fetch** -- objects already complete on disk resume without
  re-download (a failed fetch leaves nothing behind; a corrupt pre-place is
  caught by layers 1–2 before anything else runs), so the 18.8 GiB archive is
  never re-copied on a re-run.
- **Pre-flight + measured monitor** -- the proof demands the volume hold
  archive + base + index + slack *before* writing a byte, and records the
  measured peak (allocated blocks, not logical size), the lowest free space,
  and peak RSS while it runs.

Size reconciliation (the ticket's stale 169-vs-237.4): the base `.db` inside the
release zip is **181.833 GB = 169.35 GiB** -- both figures were the same file in
different units, read from the zip's central directory and the SQLite page-1
header (44,392,939 pages × 4096). NIST's base ships **no** indexes (page 1
`sqlite_master`: 5 tables + the view, zero `CREATE INDEX`), so provision builds
`idx_md5`/`idx_sha1`/`idx_sha256` over the ~438M FILE rows, growing the working
database ~40% to **~255 GB = 237.4 GiB** -- the run-2 measurement, accounted for
by index pages with no zero tail (the proof re-verifies allocated blocks vs
logical size on the real volume before it records the figure).

Run: devcontainer (`nsrlproof-wt`, python:3.14-slim), `work` = the operator's
`raw/` set, data published beside it, out of CI.

- 15:10Z: first run — pre-flight passed (need 271.8 GiB, free 550.5 GiB),
  extraction + layer 2 + index build completed, then the run **refused
  safely** (no manifest written, no volume published; cleanup restored the
  space) at the first Delta apply: `sqlite3.OperationalError: unrecognized
  token: "'._Icon;"`. Root cause: the run's extract scratch dir
  (`raw/extracted/`) still held a stale `._RDS_2026.06.1_modern_minimal_delta.sql`
  — a macOS AppleDouble twin left by an earlier crashed run — whose name also
  *ends with* the real script's, and `driver._find` matched by `endswith`:
  a 45-byte metadata blob was served to the Delta apply as the `.sql` (the
  zips themselves are clean; NIST ships no `._*` files).
- Fixed (in the driver, committed with this ticket): `_find` rejects
  dot/underscore-prefixed names (metadata twins are never NIST data files)
  and `_extract` rebuilds its destination tree from scratch (a stale file
  from a crashed run can never survive into a new one); `apply_delta`'s
  stream additionally refuses any statement that cannot begin with a SQL
  keyword, so the class fails in milliseconds with a clear message. 94
  passed in the devcontainer, pylint clean.
- 17:41Z (09-21): rerun with the fixes died in the index build when the
  small volume filled (the pre-existing failure class ADR-0007 exists to
  remove). Left 187 GiB of detritus; cleaned, then ADR-0007 was designed
  in (see above).
- 2026-09-24 ~19:05Z: **the completed run** — `realdata_turnkey_proof.py`
  in the `nsrllookup-dev` devcontainer on real artifacts (`RDS_2026.03.1`
  base + `2026.06.1` + `2026.09.1`), fetch resumed from the operator's
  `raw/`, all unbounded. **All twelve checks PASS:**

  | stage | measured |
  |---|---|
  | pre-flight | need 271.8 GiB (169.3 base + 74 GiB index budget + 27 slack) vs 605.5 GiB free → OK |
  | turnkey run (fetch-resume + 3 verify layers + 2 in-place Delta applies + record + write) | 315.3 min |
  | final volume | 252.6 GiB, allocated blocks == logical size (**zero tail verified**) |
  | peak disk (monitored, allocated) | **252.6 GiB — equal to the final volume; the ADR-0007 bound (archive + one database, never a third copy) is measurably true** |
  | peak RSS | 126 MiB (streamed digest + batched apply + in-DB index; RAM stays flat) |
  | published token == NIST's real `481e5f55…` | PASS (manifest) |
  | recipe `2026.03.1 + [2026.06.1, 2026.09.1]` | PASS |
  | delta-apply lookup discrimination (2026.09.1-inserted digest KNOWN; absent digest UNKNOWN; digest present in the 2026.09.1 `.sql`, absent from the 2026.06.1's) | PASS |
  | `verify` READY / `/health` ready / `/check` (both answers carry the real token) | PASS |

  Notes: index build grew the working database to 252.6 GiB (the estimate
  in this section said ~237.4 GiB; the three B-tree indexes over the ~438M
  FILE rows came in ~15 GiB over the 74 GiB budget, still far inside the
  volume's 605 GiB). The monitor's `min free` line reflects the launch-time
  host sample (the file-share `statvfs` inside the container is synthetic and
  is not consulted); the host volume ended the run healthy (603 GiB free /
  33% used) after the proof's cleanup removed the 252.6 GiB volume, the
  1 GiB journal, and all scratch, retaining only the NIST zips +
  `dbhashes.2026.09.1.txt` in `raw/`. Run log: `realdata_turnkey_proof`
  output captured to `artifacts/proof.log`.

**Resolution:** the turnkey path is proved on the real thing, uncapped, on a
small machine: real fetch (resumed from operator artifacts) → real 3-layer
integrity → real in-place Delta applies → real published token → real
verify/health/check, with the disk peak measured at exactly one full database
plus the archive and RAM at 126 MiB. Every `## OOM status` fix and every
ADR-0007 bound held under real load. Resolved.
