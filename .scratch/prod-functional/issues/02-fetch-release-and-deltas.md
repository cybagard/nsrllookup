# 02: Fetch the Release and Delta releases from NIST

**What to build:** the turnkey **Provisioner** driver gains the **fetch** stage: it pulls the
full **Release** zip plus its ordered **Delta release** zips — each with its `.sha` sidecar —
and the per-release `dbhashes.txt` / `signatures.txt`, from NIST's distribution, ahead of any
verify/apply/write. NIST distributes RDS V3 from a per-**Release** S3 path whose listing is
**access-denied** but whose individual objects are **public-read**, so the fetch **probes
exact object names** derived from the **Release** and **Delta release** identifiers rather
than listing the bucket. This is the slice that makes "bring a fresh box online" start
without hand-assembling the download list. The multi-gigabyte fetch is the operator's step
and is never a build or CI step (ADR-0003); this ticket wires *where the driver fetches from*,
not the heavy download itself. No new dependency.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The driver fetches the full-Minimal **Release** zip + `.sha` sidecar and each ordered
         **Delta release** zip + sidecar, plus the per-release `dbhashes.txt` and
         `signatures.txt`, by exact object names on NIST's per-Release path.
- [x] Object names are derived from the **Release** and **Delta release** identifiers, not
        hard-coded URLs.
- [x] A failed or missing object surfaces clearly (no silent empty fetch).
- [x] No new third-party dependency is introduced; the fetch reuses stdlib.
- [x] The heavy multi-GB download is documented as the operator's step, out of CI (ADR-0003).
