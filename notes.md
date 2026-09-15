# Notes / Considerations

## Python 3.14 compatibility

Checked on Python **3.14.7** (the `.venv` interpreter). **No action required.**

- `api/requirements.txt` is already the 3.14-compatible, fully-pinned set:
  `Flask==3.1.3`, `waitress==3.0.2`, `pytest==8.4.2`, `pytest-cov==5.0.0`,
  `coverage==7.15.4`. A clean-install dry-run on 3.14 resolves with a `cp314`
  wheel for the one non-pure dep (`MarkupSafe 3.0.3-cp314-…`); the venv's
  installed set matches the file exactly; `pytest --cov` passes the fixture
  suite (**76 passed, ~97%**).
- `requests`, `requests-mock`, and `urllib3` are **not needed**: nothing imports
  them — only stdlib `urllib.request` is used (the fetch path in
  `provision.fetch_set`). They are dead entries; they don't need installing and
  are already absent from the committed file.
- The CI workflow (`.github/workflows/test.yml`) already targets
  `python: 3.14` and runs the self-contained fixture suite (no Hash Set, no live
  server). No workflow change is required.
- Which libs matter: `Flask` + `waitress` are the runtime boundary/server;
  `pytest`/`pytest-cov`/`coverage` are CI-only. The HTTP boundary and lookup
  paths use stdlib + these; nothing else is load-bearing.

## Open item: the in-RAM index OOMs on real data — RESOLVED and committed

Both OOM failure modes the earlier HEAD (`3556c3e`, ticket 03) carried are fixed
and committed (`0af05af`, "In-database hash index + streamed delta apply +
trust-the-mount"):

- **In-RAM `Set[str]` materialisation → in-DB `CREATE INDEX`.** HEAD's
  `hasheset.HashSet.__init__` materialises **all** distinct digests per
  Algorithm (MD5/SHA-1/SHA-256, ~430 M each) into in-RAM Python `set()`s →
  tens of GB → OOM on a real Minimal release. The working tree replaces this
  with a per-Algorithm B-tree `CREATE INDEX` (`idx_md5`/`idx_sha1`/`idx_sha256`)
  built **inside the Hash Set's own `.db`**; a lookup is an indexed on-disk seek,
  so the digest data lives in the database file, not the process, and a lookup
  materialises no in-RAM digest copy. Validated by
  `.scratch/prod-functional/ram_sized_index_proof.py`:

  ```
  rows=     50000  build+lookup   0.06s   peak_rss_delta=  3.1 MiB   index=   8028 KiB
  rows=    500000  build+lookup   0.67s   peak_rss_delta=  0.1 MiB   index=  80756 KiB
  rows=   5000000  build+lookup   7.49s   peak_rss_delta=  2.8 MiB   index= 807452 KiB
  ```

  Peak RSS is **flat** (~0.1–3.1 MiB) from 50 K to 5 M rows while the index
   grows on-disk (8 KiB → 800 KiB). The OOM (RSS scaling with the
  distinct-digest count) is gone: the index is the db, not the process.
- **Whole-delta `executescript` + per-Delta `copyfile` of the ~169 GB base →
  streamed + batched apply.** HEAD's `hasheset.apply_delta` feeds the **whole**
  Delta `.sql` (the 2026.09.1 release alone is ~1 GB / 3.8 M `INSERT`s) to
  `executescript` (`query string is too large`) and `copyfile`s the ~169 GB
  extracted base **per Delta** → disk blowup (one run took the disk to 87%
  full). The working tree applies a Delta **streamed** via
  `hasheset._apply_sql_stream(conn, delta_sql, batch=100_000)` — one `INSERT`
  at a time, committing every `batch` statements — so neither the full text nor
  a mega-transaction is ever held at once (ADR-0003).

**Status of the fix:** committed in `0af05af` on `main` (ahead of
`origin/main`, not yet pushed). `HashSet.__init__` opens a single `mode=ro`
connection per ADR-0001/0006, so a boot/verify entry trusts the mounted db and
does not rebuild the index; the **Provisioner** and **Delta** apply are the only
writable paths, building the per-Algorithm **hash index** into the same `.db`.
