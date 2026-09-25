# Bound the turnkey run's disk footprint: one database, never three

The turnkey flow on real NIST data does not fit a small machine as originally
wired. Measured from the real artifacts (the 2026.03.1 `modern_minimal`
release zip's central directory and its SQLite page-1 header): the 18.775 GB
Release archive unpacks to a **181.833 GB** (169.35 GiB) base `.db` of
44,392,939 pages. That base ships **no indexes** (page 1's `sqlite_master`
carries the five tables + the `DISTINCT_HASH` view and zero `CREATE INDEX`),
so provision builds `idx_md5`/`idx_sha1`/`idx_sha256`, growing the working
database ~40% to ~255 GB (**237.4 GiB** -- the run-2 measurement, accounted
for by index pages, no zero tail). The pre-existing pipeline materialised, in
succession: the fetch copy (~19 GiB), the extraction (169.4, transiently
doubled by the base copy), **a second full copy per Delta in system scratch
(copy-on-apply)**, and **a third full copy into the data dir** -- peaking well
past 500 GiB even with scratch hygiene deleting superseded copies. That peak
neither fits the Docker Desktop VM (8 GiB RAM, `Docker.raw` ext4 -- the
measured death was a write-EIO storm at 07:17Z on 2026-09-21) nor a host pool
of ~170–450 GiB. We therefore bound the turnkey run's peak at **one full
database plus the archive**.

- **Status**: accepted
- **Considered Options**: raise the Docker Desktop VM's RAM and retry the
   unbounded run (rejected: it papers over over-allocation -- the run
   *allocates* 500–730 GiB, so a small machine runs out of disk regardless of
   cache); a second hardware volume for the apply copy (rejected: a small
   machine does not have one); stream the base from the zip without
   extracting (rejected: SQLite needs a real file, and layer 2 must verify the
   extracted tree anyway); keep the run unbounded and only *capped* proofs
   (rejected: the ticket 04 real-data acceptance criteria demand the uncapped
   driver on real artifacts). Instead, three mechanisms keep the peak at one
   full database + the archive: (1) **in-place delta apply on scratch** --
   `hasheset.apply_delta(..., in_place=True)` applies the ordered `.sql`
   (streamed per ADR-0008) to the working database itself, so no second
   full copy exists; the driver routes
   in-place only when the current database resolves inside the run's scratch
   roots (the working copy derived from the verified archive, which is
   disposable), and keeps **copy-on-apply** for any database outside them (a
   trusted mounted volume is never altered -- ADR-0005 stands); (2)
   **same-volume rename publish** -- the extracted base and the finished
   database enter their next stage by `os.replace` (an O(1) rename) when
   source and destination share a filesystem, the common layout, falling back
   to a streamed copy only across volumes; (3) **resumable fetch** -- a
   Release or Delta **archive** already complete on disk is trusted without
   re-download: a failed download leaves nothing behind (an existing target
   is complete by construction), and a corrupt or pre-placed archive is
   caught by the integrity layers (1–2) before anything else runs, so a
   rerun never re-copies the ~19 GiB archive. The Release's `dbhashes.txt`
   fetches through the same helper and resumes under the same rule, but it
   is a small **text object with no signature layer of its own**: its
   integrity rests on the fetch itself (TLS to NIST) and on the per-Release
   filename, which bounds a stale local copy to that same Release's object.
   A stale or tampered copy would surface only as a wrong attested token in
   the manifest -- the data plane is unaffected -- so this is a documented
   residual risk: `make verify` is a local record-and-attest comparison
   (manifest against the in-database provenance, both derived from the same
   file, ADR-0006) and re-checks nothing external; the real-data proof
   (ticket 04) additionally checks the recorded token against NIST's known
   value.
- **Consequences**: the Modern Minimal turnkey run peaks at ~260 GiB on one
   volume (the 18.8 GiB archive + the ~237.4 GiB indexed database; ~188 GiB
   at extraction) and steady at ~256 GiB, and needs that much on the work
   volume plus a data volume for the rename (or a cross-volume copy, 2× volume
   in that layout) -- a machine that can hold the archive + the indexed
   database can run the whole path; a failed apply corrupts only the
   disposable working copy (the archive is the source of truth and the
   **Provisioning manifest** is written only on success, so ADR-0005's
   never-serve-unverified guarantee is unchanged); the Docker Desktop VM holds
   no multi-hundred-GiB files of its own (its disk never again carries an
   apply copy), so the dev container is a safe place to *run* the pipeline
   with the heavy I/O on the mounted workspace; the driver's external contract
   (`make provision` / `make verify`) is unchanged.
