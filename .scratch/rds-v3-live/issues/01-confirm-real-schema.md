# 01: Byte-confirm the real NIST Minimal `FILE`/`DISTINCT_HASH` schema

**What to build:** a confirmed view of NIST's **real** RDS V3 **Minimal** on-disk layout —
superseding ticket `04` of `rds-v3-migration`, which "confirmed" a synthetic `METADATA`
table that NIST does not publish. From NIST's shipped `schema.sql`/`signatures.txt` (the
~206 MiB `RDS_<ver>_<set>_minimal_delta.zip` ships both) record the authoritative schema:
the `FILE` table columns, the `DISTINCT_HASH` view, the absence of `md5sha1`, `file_name`
vs `filename`, and the digest casing.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The real **Minimal** `FILE` table is documented with its authoritative column set
       (`sha256, sha1, md5, crc32, file_name, file_size, package_id`) and the `DISTINCT_HASH`
       view (`sha256, sha1, md5, crc32`).
- [x] The `METADATA`/`md5sha1`/`filename` synthetic layout is **refuted**: confirmed absent
       from the real schema, with a pointer from this ticket to ticket `04` as superseded.
- [x] Digest **casing** in the real db is recorded (expected UPPERCASE in presentation;
       confirm stored form), so ticket 02 can fix the normalisation side.
- [x] The confirmation cites the NIST artifact it came from (shipped `schema.sql`), recorded
       for ticket 02 to rebuild the fixture in the real shape.

## Answer

Byte-confirmed against NIST's shipped `schema.sql` for **Modern Minimal, release
2026.09.1**. The authoritative artifact and its integrity evidence are staged verbatim in
`.scratch/rds-v3-live/artifacts/extracted/` (see that folder's `README.md`); the heavy
zip + `.sha` live in `…/artifacts/raw/` and are gitignored.

**Source + integrity (all three layers, verified this session).**
- Artifact: `…/extracted/schema.sql` = NIST's
  `RDS_2026.09.1_modern_minimal.schema.sql` (1,519 bytes), inside
  `RDS_2026.09.1_modern_minimal_delta.zip` (185,084,394 bytes = 177 MiB).
- Layer 1 (transport): zip SHA-1 = `fc23ae7332b9188a089baf8fb53b9a6b463701d5`, matching
  the shipped `…_zip.sha` sidecar **and** the `modern minimal delta` line of
  `…/extracted/version.txt`.
- Layer 2 (contents): `SHA256(schema.sql)=b37a8c53dcc81a00828f7e53177b1c38c90dde8dee83a012d5ec56a8cc24ca72`
  and `SHA256(readme.txt)=b42a0e7ae3fc623fd140a9534a9bc938e9cdedf6820b1a8e30dbe4b7e64251cb`,
  both matching `…/extracted/signatures.txt`.
- Layer 3 (dataset): the Modern Minimal dbhash chain in `…/extracted/dbhashes.txt`
  (`481e5f55f6d1ed63ea0f176779efc5cc5d53e52a RDS_2026.09.1_modern_minimal.db`, built in
  order from `RDS_2026.03.1_modern_minimal.db` + the `06.1`/`09.1` minimal deltas).

**The real Minimal `FILE` table (from `schema.sql`).**
```
CREATE TABLE FILE (
  sha256     VARCHAR NOT NULL,
  sha1       VARCHAR NOT NULL,
  md5        VARCHAR NOT NULL,
  crc32      VARCHAR NOT NULL,
  file_name  VARCHAR NOT NULL,
  file_size  INTEGER NOT NULL,
  package_id INTEGER NOT NULL,
  CONSTRAINT PK_FILE__FILE PRIMARY KEY (sha256, sha1, md5,
         crc32, file_name, file_size, package_id)
);
```
The column order and names match the design exactly; `crc32` is a physical column but is
**not** a supported lookup Algorithm. The full primary key spans all seven columns.

**The `DISTINCT_HASH` view (from `schema.sql`).**
```
CREATE VIEW DISTINCT_HASH AS
  SELECT DISTINCT sha256, sha1, md5, crc32 FROM FILE;
```
This is the table the Sidecar index materialises (per `hash_counts.txt`, ~73,778,779
distinct SHA-256 in Modern Minimal) rather than scanning the ~441,621,230 raw `FILE` rows.

**Other tables shipped in the real layout** (context; not consulted by lookup):
`MFG(manufacturer_id, name)`, `OS(operating_system_id, name, version, manufacturer_id)`,
`PKG(package_id, name, version, operating_system_id, manufacturer_id, language,
application_type)`, `VERSION(version, build_set, build_date, release_date, description)`.
`FILE.package_id` is a foreign key into `PKG`.

**Refutation of the synthetic layout (migration ticket 04).**
- `METADATA` — **absent.** No table by that name in `schema.sql`; the per-file table is
  named `FILE`.
- `md5sha1` — **absent.** Not a column anywhere in `FILE` (or `DISTINCT_HASH`).
- `filename` — **absent; the real column is `file_name`.**
- `file_size`, `package_id` — **present** in real `FILE`, absent from the synthetic fixture.
- The synthetic 6-column `METADATA(crc32, md5, md5sha1, sha1, sha256, filename)` was
  invented; it is superseded by `FILE` above. See `04` (superseded) below.

**Digest casing (for ticket 02's normalisation).** Stored **UPPERCASE**, confirmed from the
real delta head (`unzip -p … RDS_2026.09.1_modern_minimal_delta.sql`, ~64 KiB sampled):
`INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,package_id)
VALUES('00000296EB569C19B0F2BD73B481392A76A0B4DC6FEBD52483E967D12F41AE50',
'E35A81EA9EC466808C35C0A117E6E9922352CCE','0662DE95E370A6F800E149E240FB0BDE',
'7D227EE3','27…',…)`. The sidecar index must UPPERCASE stored digests (and the input) so
membership is case-agnostic, as already designed.

**Delta shape (for tickets 04/07).** The real delta is a `.sql` text script
(`BEGIN TRANSACTION;` then `INSERT INTO FILE(sha256,sha1,md5,crc32,file_name,file_size,
package_id) VALUES (…)`, …), applied to the prior full `…_minimal.db` in order — not a
table of row-dicts. `readme.txt` (`delta.readme.txt`) states the delta "is intended to
update the previously published full modern SQLite3 database."
