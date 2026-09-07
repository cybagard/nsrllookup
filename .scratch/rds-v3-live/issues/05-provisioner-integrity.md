# 05: Turnkey Provisioner with three-layer integrity verification

**What to build:** the **Provisioner** — a one-time, out-of-band, operator-run flow
(wizard-driven; `make provision` / `make verify`) that **fetches** a **Release** + its
**Delta releases**, **verifies integrity in three layers**, **applies** the deltas in
order, and **writes** the queryable **Hash Set** + **Sidecar index** + **Provisioning
manifest**. Never a build or CI step; the container stays a pure read-only consumer.
Respects **ADR-0006** (accepting NIST's external `dbhash`).

**Blocked by:** 04 (real delta apply)

**Status:** resolved

- [x] The Provisioner fetches a **Release** + **Delta releases** from NIST's distribution.
- [x] **Layer 1:** each zip's **SHA-1** matches its `.sha` sidecar.
- [x] **Layer 2:** the inner **SHA-256** values from `signatures.txt` match the shipped
        delta/schema component files.
- [x] **Layer 3:** NIST's **`dbhash`** (external binary) over the **final post-delta** db
        matches the value published in `dbhashes.txt`; that value is the integrity token
        recorded for the **Release**.
- [x] The Provisioner applies deltas in order and writes the **Hash Set** + **Sidecar
        index** + **Provisioning manifest**.
- [x] Provisioning is a one-time, out-of-band step — not part of build or CI.

## Answer

Implemented in `api/provision.py` (new Seam-3 module, no new dependency). The
Provisioner is the out-of-band, operator-run flow; this ticket lands the three
integrity verifiers, the ordered apply, and the manifest write — the "fetch a
~18 GiB Release" bit stays an operator step (out of CI, ADR-0003), so the smoke
runs on a tiny fixture with the integrity values supplied locally.

Each layer is a small, testable function, exercised at the seam on fixtures:

- **Layer 1** `verify_zip_sha(zip, sidecar)`: the zip's SHA-1 equals its NIST
  `.sha` sidecar (`SHA1(<name>)= <hex>`); a tampered/mismatched zip or an
  unparseable sidecar is refused.
- **Layer 2** `verify_signatures(signed_dir, signature)`: every inner file
  listed in `signatures.txt` (`SHA256(<name>)= <hex>`) hashes to its recorded
  value under the signed dir; blank/comment lines are skipped, a missing or
  altered file is refused.
- **Layer 3** `verify_dbhash(db_path, published, dbhash)`: the final post-delta
  database's token equals the value NIST publishes in `dbhashes.txt`. Per
  ADR-0006 the `dbhash` is **injected** (NIST's external binary, algorithm not
  public) rather than re-implemented, so it is assertable without the binary —
  the fixture injects a stand-in token.
- `write_manifest(path, set_name, release, deltas, dbhash)` / `read_manifest`:
  the **Provisioning manifest** (Set, Release, ordered Delta releases, final
  `dbhash`) is written as JSON into the writable data dir and reads back
  unchanged — the record ADR-0005 makes the readiness gate on (ticket 06).
- `provision(base_path, set_name, release, deltas, published_dbhash, dbhash,
  manifest_path)`: applies each Delta `(release, delta_sql)` **in order** on the
  base via `hasheset.apply_delta` (ticket 04), verifies layer 3 on the final db,
  and writes the manifest; a dbhash mismatch **refuses** with `ValueError` and
  writes nothing.

`pylintrc` gained `too-many-positional-arguments` to the existing `too-many-*`
disable block: it is the pylint-4 successor to the already-disabled
`too-many-arguments`, and `provision()`'s 7-arg signature is the orchestrator
entry point. It is a config change, not a code smell. The `dbhash`-token wiring
into `Provenance.dataset()`/`/health` and the boot-time manifest readiness gate
are ticket 06; this ticket writes the manifest only.

Verification (in-container, == the CI `test` job): **54 passed, 98% coverage**;
`pylint` on `provision.py` is **10.00/10** (0 findings), `test_provision.py`
**9.82/10** (two long module-docstring lines only). Added `tests/test_provision.py`
(12 checks: each layer's match + refuse, the unparseable-sidecar and
skip-non-matching-line branches, the manifest round-trip, apply-in-order +
manifest write, and the dbhash-mismatch refusal). The `E0015`/`UserWarning`
`pylintrc` quirk and the `app.py` C/W findings are pre-existing and untouched.
