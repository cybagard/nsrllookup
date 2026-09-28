# Spec: Make nsrllookup fully production-functional

Status: ready-for-agent

The service logic is complete and test-green (60 passed, ~98% coverage); the API and
lookup seams are prod-ready. This spec closes the one remaining gap that decides whether
the service is *fully* prod-functional for a forensic user: the **Provisioner**'s integrity
and turnkey path. Today layer 3 of integrity (the dataset **`dbhash`**) is only ever an
injected stand-in in tests — nothing records NIST's real published token — and there is no
turnkey driver that takes a fresh box to a verified **ready** state. An operator cannot
actually bring a box online today. This spec makes the Integrity token real, adds the
turnkey **Provisioner** driver, proves it on real NIST artifacts out-of-CI, and folds in the
stale-tracker housekeeping. It respects ADR-0001..0006 and uses the vocabulary of
`CONTEXT.md`.

## Problem Statement

From the user's (operator's + forensic consumer's) perspective: nsrllookup *looks*
deployable but is not yet one box away from trusted production.

- **The dataset cannot be truly verified.** The service's entire trust model is "a
   **Lookup Result** is only trustworthy through the **dataset** that answered it"
  (ADR-0005). But the third and decisive integrity layer — NIST's **`dbhash`** over the
  final post-delta database — is never actually obtained. In the current design the
   **Provisioner**'s layer-3 check compares a *computed* token against the published one,
  and the only `dbhash` callable that exists is a test stand-in. Because NIST's `dbhash`
   bit-level algorithm is not public (ADR-0006), it cannot be recomputed, so a real
   provisioning run has no layer-3 to perform. A "verified" volume today is verified in
   layers 1–2 only; the token a forensic consumer would re-verify against
   `dbhashes.txt` is a stand-in, not NIST's published value.
- **There is no turnkey path to a verified `ready` state.** `docker-compose.prod.yml`
   mounts a `./data` volume but nothing *produces* it; the spec's promised
   `make provision` / `make verify` do not exist (no `Makefile`, no fetch/driver
   orchestration). An operator cannot bring a fresh box to a trusted ready state in a
   single scripted step.
- **It has never been run against real data.** The only deploy proof is fixture-based;
   the real-data mechanics smoke (ticket 07) exercised the reader + delta apply on a
   *different* (curated) schema with a stand-in token. The turnkey path on a real
   Minimal **Set** has never been driven end to end.
- **The tracker lies.** Every `.scratch/triage/issues/*` still carries `Status: open`
   though tickets 01–09 are committed and the work is resolved; a new agent or human
   would misread the project as entirely unstarted.

## Solution

From the user's perspective:

- **Make integrity real by *recording* NIST's published token, not recomputing it.** The
   **Provisioner**'s layer 3 reads the **`dbhash`** NIST publishes in that **Release**'s
   `dbhashes.txt` and records it as the dataset's **Integrity token** in the
   **Provisioning manifest**. It does **not** recompute the token (the algorithm is not
   public, ADR-0006); it *attests* it. This is a refinement of ADR-0006 ("the Provisioner
   runs NIST's `dbhash`" → "the Provisioner records NIST's published `dbhash`") and keeps
   ADR-0005's design intact: the service trusts the verified mount and the manifest is the
   token it checks at boot.
- **Give the operator one command.** A turnkey `make provision` driver owns the full
   out-of-band flow — **fetch → verify (3 layers) → apply Delta releases in order → write**
   the queryable **Hash Set** + **Sidecar index** + **Provisioning manifest** — and is
   proven on real NIST artifacts by actually running it out-of-CI. `make verify` re-checks
   an already-provisioned volume. The multi-gigabyte **Release** fetch stays the operator's
   step (ADR-0003: never at build or CI); the driver orchestrates, the human runs it.
- **Prove the mechanics on a real Minimal artifact, out-of-CI.** Drive the turnkey path on
   real NIST objects so layer 3 is a *real published token*, recorded in the manifest, not a
   stand-in. The full ~18 GiB download and the production host are the operator's; the
   proof records that the path itself is real.
- **Set the tracker straight (folded in).** Resync the stale `.scratch/triage/issues/*`
   `Status:` lines so the tracker reflects that 01–09 are resolved.

## User Stories

1. As an operator, I want `make provision` to take a fresh box to a verified **`ready`**
   state with one command, so that bringing the service online is a single scripted step.
2. As an operator, I want the turnkey driver to **fetch** the full **Release** and its
   ordered **Delta releases** from NIST's distribution, so that I do not hand-assemble the
   download list.
3. As an operator, I want the driver to **verify integrity in three layers** — layer 1 the
   zip **SHA-1** against its `.sha` sidecar, layer 2 the inner **SHA-256** values against
   `signatures.txt`, layer 3 NIST's published **`dbhash`** from `dbhashes.txt` — so that
   the **Hash Set** is trusted before the service answers against it.
4. As an operator, I want layer 3 to **record NIST's published `dbhash`** for the
   **Release** into the **Provisioning manifest** without the driver having to recompute it,
   so that provisioning works even though NIST's token algorithm is not public (ADR-0006).
5. As an operator, I want the driver to **apply the Delta releases in order** onto the full
   **Release** and **rebuild the Sidecar index**, so that the **Hash Set** is the most
   current **Set** NIST publishes without a full re-download.
6. As an operator, I want the driver to **write the queryable Hash Set + Sidecar index +
   Provisioning manifest** into the data dir, so that `docker-compose -f
   docker-compose.prod.yml up -d api` finds a ready-to-serve volume.
7. As an operator, I want `make verify` to **re-check an already-provisioned volume**
   (manifest present, layers hold), so that I can confirm a volume is still trusted before
   trusting it.
8. As an operator, I want the multi-gigabyte **Release** fetch to be **my step and never a
   build or CI step**, so that a multi-GB dataset never transits the pipeline (ADR-0003).
9. As a forensic consumer, I want the **`dbhash`** recorded in the **Provisioning manifest**
   and surfaced on every **Lookup Result** and on **`/health`** to be **NIST's published
   token**, so that I can re-verify any answer against NIST's `dbhashes.txt`.
10. As a forensic consumer, I want the recorded token to reflect the **final post-delta**
    database, so that an answer's dataset identity names the exact **Release** + applied
    **Delta releases** it was checked against.
11. As a security reviewer, I want every **Lookup Session** — successful or rejected — to
    still produce a durable **Audit Entry** (unchanged, ADR-0004), so that the public
    interface stays forensically accountable.
12. As a maintainer, I want the new work to live in the **Provisioner / data side (Seam 3)**
    plus a thin turnkey driver, with the **API boundary (Seam 1)** and the **lookup module
    (Seam 2)** untouched, so that the change stays concentrated.
13. As a maintainer, I want the turnkey driver to use the **existing** layer verifiers
    (`verify_zip_sha`, `verify_signatures`) unchanged and to add only a *record-the-published*
    path for layer 3, so that the proven behavior is not disturbed.
14. As a maintainer, I want the real-data proof to run **out-of-CI** and be recorded, not
    added to the automated suite, so that multi-GB I/O never blocks a PR (Testing Decisions).
15. As a downstream integrator, I want the **Provisioning manifest** shape and the **Lookup
    Result** `dataset` block to stay stable (Set, Release, ordered Delta releases, final
    `dbhash`), so that I can code against them with confidence.
16. As a maintainer, I want the stale `.scratch/triage/issues/*` **`Status:`** lines
    resynced to reflect 01–09 resolved, so that a new agent or human does not misread the
    project as unstarted.
17. As an operator, I want the driver to refuse to write a **Provisioning manifest** if any
    integrity layer fails, so that an unverified or partially-applied **Hash Set** can never
    be served (ADR-0005).
18. As an operator, I want the driver to be **idempotent in order** — applying a Delta
    release already recorded in provenance is a no-op for the ordered list — so that a
    re-run does not duplicate deltas.
19. As a forensic consumer, I want **`/health`** to keep reporting **`ready`** only when the
    **Provisioning manifest** is present and its integrity still matches the mounted **Hash
    Set**, so that a stale volume never answers (ADR-0005).
20. As an operator, I want a clear, single source of the per-Release `dbhashes.txt` token
    (fetched/downloaded by the driver and recorded), so that the token in the manifest is
    auditable to NIST.

## Implementation Decisions

- **Seams (ideal number one).** All new work lands in **Seam 3 — the Provisioner / data
   side** (`provision.py`) plus a **thin turnkey driver** that orchestrates it. **Seam 1
   (the HTTP/API boundary)** and **Seam 2 (the lookup module)** are **unchanged**: they are
   already prod-ready. No new automated test seam is introduced; the driver is proven by
   *running it on real NIST objects out-of-CI* (per the existing Testing Decisions and
   ticket 07), not by a fresh in-suite seam.
- **Layer 3 becomes "record the published token", not "compute and match".** The bit-level
   `dbhash` algorithm is not public (ADR-0006), so it cannot be recomputed. The Provisioner's
   layer-3 step **reads NIST's published `dbhash` for the **Release** from that release's
   `dbhashes.txt`** and **records it as the Integrity token** in the **Provisioning
   manifest**. This *refines* ADR-0006's consequence ("the Provisioner runs NIST's `dbhash`"
   → "the Provisioner records NIST's published `dbhash`"); ADR-0006 should be updated to say
   the token is *recorded* (attested), not recomputed, since the algorithm is not public.
   ADR-0005 is unchanged: the **Provisioning manifest** is still the integrity token the
   service checks at boot, and the service **trusts the verified mount**.
- **The existing layer-1/layer-2 verifiers are reused unchanged.** The turnkey driver
   keeps `verify_zip_sha` (zip **SHA-1** vs `.sha` sidecar) and `verify_signatures` (inner
   **SHA-256** vs `signatures.txt`) as-is; only the layer-3 path changes from a
   compute-and-compare `verify_dbhash(db, published, dbhash)` to a **read-and-record** that
   captures the published token and writes it into the manifest. (The current
   compute-and-compare `verify_dbhash` remains only as the stand-in used by the fixture
   suite; the *turnkey* path uses record-and-attest.)
- **Turnkey driver + `Makefile`.** Add a turnkey **Provisioner driver** (a single
   orchestration entry) plus a **`Makefile`** exposing **`make provision`** and
   **`make verify`** — the surface the `rds-v3-live` spec already promised but that
   does not yet exist. `make provision` owns the full flow: **fetch** the full **Release**
   zip + its ordered **Delta release** zips from NIST's distribution, **verify** all three
   layers, **apply** the deltas in order (via the existing `hasheset.apply_delta`
   `executescript` mechanism), **record** the published `dbhash`, and **write** the
   queryable **Hash Set** + **Sidecar index** + **Provisioning manifest** into the data
   dir. The driver orchestrates; the multi-gigabyte **fetch is the operator's step** and is
   **never a build or CI step** (ADR-0003). `make verify` re-runs layer checks + the
   manifest/readiness check against an already-provisioned volume.
- **Fetch mechanics.** NIST distributes RDS V3 from the per-release S3 path (anonymous
   bucket **listing is access-denied**, but individual objects are **public-read**), so the
   driver **probes exact object names** under the per-Release path rather than listing.
   Objects are the full-Minimal **Release** zip + its `.sha` sidecar, the per-**Delta
   release** zip(s) + sidecars, and the **terminal release's** `dbhashes.txt`. There is no
   top-level `signatures.txt` on NIST (live probes 403; the release README lists the
   objects without one) — each archive carries its *inner* `signatures.txt`, which the
   signature layer verifies from the extracted tree — so the plan carries exactly one
   per-Release text object, and it is the terminal release's `dbhashes.txt`.
   The driver does not hard-code a single URL; it derives object names from the **Release**
   and **Delta release** identifiers.
- **Bounded footprint.** The uncapped turnkey run is bounded at one full **database** plus
  the archive — ~260 GiB on one volume for the current Set (ADR-0007): the Deltas apply
  **in place** on the run's scratch working copy (copy-on-apply remains the protection for
  trusted mounted volumes, ADR-0005), the extracted base and the finished database publish
  by **same-volume rename** (a streamed copy only across volumes), and the fetch **resumes**
  objects already on disk. The real-data proof (ticket 04) pre-flights the volume and
  records the measured peak, so the run fits a small machine in the dev container instead
  of the previous 500–730 GiB peak that took the Docker VM's ext4 down.
- **Manifest + provenance unchanged in shape.** The **Provisioning manifest** keeps its
   fields (Set, Release, ordered Delta releases, final `dbhash`) and the **Lookup Result**'s
   `dataset` block keeps `set`, `release`, ordered `deltas`, `dbhash` — stable contract for
   downstream integrators (user story 15). The recorded `dbhash` is now NIST's published
   value rather than a stand-in.
- **Readiness gate unchanged.** Boot still reports **`ready`** only when the **Provisioning
   manifest** is present and its integrity matches the mounted **Hash Set** (ADR-0005 /
   `verify_readiness`); the service still **trusts the verified mount** and does **not**
   recompute `dbhash` at boot (ADR-0006).
- **No new dependency.** The driver reuses stdlib (`hashlib`, `sqlite3`, `subprocess`/urllib
   as needed for fetch) and the existing `provision.py` verifiers; no new third-party
   package.
- **Tracker housekeeping (folded in).** Resync the stale `.scratch/triage/issues/*`
   **`Status:`** lines to `resolved` to match the committed 01–09 work (or retire the stale
   `triage` effort dir). This is a housekeeping item, not a code change.

## Testing Decisions

- **What makes a good test here.** Continue the established rule: tests assert **external
   behavior at a seam**, never SQL or index internals. The driver's automated test asserts
   the orchestration *shape* on a fixture — fetch is stubbed, the three layer verifiers run
   on fixture artifacts, deltas apply in order, a mismatch **refuses** the manifest write,
   and the written **Provisioning manifest** round-trips through `read_manifest` with the
   right fields. The driver is **not** asserted on real multi-GB I/O.
- **Which modules are tested.** The **Provisioner / data side (Seam 3)** — the new
   turnkey driver and the record-and-attest layer-3 path — via a fixture-based driver test
   (fetch stubbed). The **API boundary (Seam 1)** and **lookup module (Seam 2)** keep their
   existing tests; nothing there changes. The existing `verify_zip_sha` /
   `verify_signatures` fixture tests stand unchanged.
- **Prior art.** The fixture tests in the current suite are the template:
   `test_provision.py` (each layer's match + refuse, unparseable-sidecar, skip-line,
   manifest round-trip, apply-in-order + manifest write, dbhash-mismatch refusal) and
   `test_readiness.py` (present+matching manifest ⇒ ready; dbhash mismatch ⇒ not-ready).
   The new driver test extends `test_provision.py`'s style to the orchestration entry with
   fetch stubbed.
- **Real-data proof is out-of-CI and recorded, not added to the suite.** Per the
   `rds-v3-live` Testing Decisions and ticket 07, the turnkey path is proved by **actually
   running `make provision`/the driver on real NIST Minimal objects**, exercising layer 3
   with **NIST's real published `dbhash`** recorded from a real `dbhashes.txt` — closing the
   one open strand ticket 07(b) left (a curated release predates `dbhashes.txt`, so a real
   token could not be checked). The full ~18 GiB Minimal download and the production host
   stay **operator steps**, out of the automated suite (multi-GB I/O must never block a PR).
- **Automated gate stays green.** After the driver lands, the existing fixture suite
   (60 passed, ~98% coverage) must still pass plus the new driver test; `pylint` on the new
   driver must be clean (carrying the existing `too-many-*` disable convention for the
   orchestration entry point, as `provision.py`'s 7-arg entry point already does).

## Out of Scope

- **Authentication / caller identity.** The interface stays **public + audited** (ADR-0004);
   an auth toggle and a caller-supplied identity in the **Audit Entry** are separate,
   later tickets.
- **Other Sets (Legacy, Android, iOS).** Only **Modern** is in scope; selecting another
   **Set** reuses the same Minimal/delta mechanism and is a later ticket.
- **Tamper-evident audit storage.** The **Audit Trail** stays durable and append-only;
   hash-chaining / WORM hardening is not in scope.
- **Re-implementing `dbhash`.** The token algorithm is not public (ADR-0006); the driver
   **records** NIST's published value, it does not derive it.
- **Multi-GB fetch automation / production hosting.** The turnkey driver orchestrates and
   proves the path; the ~18 GiB download, the per-release cadence of delta application,
   and deploying to a specific host / scaling are operational follow-ups (ADR-0003).
- **The `rds-v3-migration` and `rds-v3-live` efforts** are complete; this spec only closes
   the production-functional gap they left (real layer-3 token + turnkey driver) plus
   tracker housekeeping.

## Further Notes

- **Why this is "fully prod functional."** The API, lookup, audit, readiness, and real-V3
   data layout are done and test-green. The only thing between "looks deployable" and a
   trusted forensic service is (a) a **real dataset Integrity token** — recorded from NIST's
   published `dbhashes.txt` — and (b) a **turnkey way to reach it** — `make provision`.
   With both, an operator can bring a fresh box to a genuinely verified **`ready`** state
   and a forensic consumer can re-verify every answer against NIST.
- **ADR-0006 refinement.** Implementing "record the published token" changes ADR-0006's
   consequence from "the Provisioner **runs** NIST's `dbhash`" to "the Provisioner
   **records** NIST's published `dbhash`." Update the ADR text on landing; the decision
   (accept `dbhash` as a provisioning-time external dependency; trust the verified mount;
   do not recompute at boot) is unchanged.
- **The recorded token vs the mount.** Because the algorithm is not public, the forensic
   guarantee that *the applied database equals what NIST published* rests on **layers 1–2
   (transport SHA-1 + inner SHA-256) plus trusting NIST's published `dbhashes.txt`**; the
   boot **readiness gate** confirms the **Provisioning manifest** is present and well-formed
   (ticket 06 in this spec closes a serving-thread gap found in the post-04 live smoke).
- **The waitress thread gap (ticket 06).** A live run of the provisioned service
   (post ticket-04 smoke) found every `POST /check` returning 500: the Hash Set's
   single read-only connection is opened on the boot thread, and CPython's `sqlite3`
   keeps connections thread-affine by default, so `waitress`' worker threads could
   never use it. The suite stayed green because the tests serve through the
   single-threaded Flask test client. Closed in ticket 06: the connection crosses
   threads (`check_same_thread=False`) with an application-held lock around the
   indexed query; no seam, ADR, or lookup contract changed.
   and that the mount carries the recorded token. This is the honest position under ADR-0006
   and is stated explicitly in the implementation decisions.
- **Stale tracker.** The `.scratch/triage/issues/*` `Status: open` lines predate the
   `rds-v3-live` commits (01–09, see `git log`); they should be resynced to `resolved` so
   the tracker reflects reality.
- **Real-data proof closes ticket 07(b)'s open strand.** `rds-v3-live/07` proved the
   reader + delta mechanics on a *curated* schema but could not check a real token (that
   release predates `dbhashes.txt`). This spec's real-data proof drives the turnkey path on
   a real Minimal **Release** that *does* publish a token, so layer 3 is a real published
   value, not a stand-in.
