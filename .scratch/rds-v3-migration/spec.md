# Spec: Migrate nsrllookup to NIST RDS V3

Status: ready-for-agent

Formal spec synthesised from the project's domain model (`CONTEXT.md`, `docs/adr/0001..0004`)
and the triage work-list in `.scratch/triage/`. This is the authoritative behavioural spec;
`.scratch/triage/spec.md` remains the high-level 8-ticket work-list, and `issues/01..08` are
the task tickets. The two must be read together.

## Problem Statement

The operator of nsrllookup can no longer run it. The reference-data ingest path — the
script that pulled the NIST set and loaded it — points at a URL that now returns 403, and
the format it consumed has been retired by NIST. So the service cannot obtain the data it
exists to serve, and "bring the project current" is blocked at the source.

Independently, the project is stale in every layer: the language runtime is end-of-life,
the dependencies are years old, the test runner is an abandoned project, and the API offers
only a single, MD5-only lookup with an undocumented-for-downstream response shape. Because
the service is a **forensic** tool, that staleness is not cosmetic: a lookup answer is
only trustworthy if it is reproducible — the consumer must know *which* dataset answered —
and the whole history of what was asked must be recoverable.

## Solution

Rebuild nsrllookup around the current NIST data model and a modern stack, keeping it usable
as a forensic reference:

- **New data source.** Migrate ingest to **NIST RDS V3** (SQLite), serving NIST's
  **Minimal** **Set** for the **Modern** **Set**, kept current by applying NIST's
  **Delta releases** on top of the current full **Release**.
- **New engine.** Replace the retired `nsrlsvr` server and its socket protocol by querying
  the **Hash Set** database directly, with a per-Algorithm **hash→known index** built at
  ingest (V3 stores digests uppercase with no standalone hash index).
- **New API.** Exchange the MD5-only `GET /check/<hash>` for `POST /check`: one request
  names one **Algorithm** (MD5, SHA-1, or SHA-256 — all first-class) and one or more
  **Digests**, returning one **Lookup Result** per digest, each carrying full provenance
  (Set, Release, applied deltas). A `/health` endpoint exposes the currently loaded
  Release + Deltas.
- **Forensic safety.** The interface is **public** (no authentication); the forensic
  guarantee is instead a durable, append-only **Audit Trail**: an **Audit Entry** is
  recorded for every **Lookup Session**.
- **Modern stack.** Move to current Python / WSGI / test tooling and make the test job a
  first-class CI step.

The end state: a current, reproducible, auditable forensic lookup service with no
dependency on any retired component.

## User Stories

1. As an operator, I want to provision the reference data by mounting NIST's **Minimal**
   **Set** as a read-only volume, so that I don't have to download the ~124 GB full
   **Set** into my environment.
2. As an operator, I want a new **Delta release** applied on top of my current full
   **Release**, so that my **Hash Set** stays the most current NIST publishes without a
   full re-download.
3. As an operator, I want the current **Release** date-version and the list of applied
   **Delta releases** visible in service configuration and on `/health`, so that I — and
   downstream consumers — always know exactly what the service is checking against.
4. As an operator, I want a **Lookup Session** to record which **Release** + **Delta
   releases** answered, so that any historical answer is reproducible and re-verifiable.
5. As an operator, I want the service to start correctly when a **Delta release** is
   applied to a **Hash Set**, so that staying current never produces a corrupt or partial
   dataset.
6. As a forensic investigator, I want to ask whether a file's **MD5** is a **Known**
   reference data file, so that I can separate benign, pre-existing files from the files
   of interest.
7. As a forensic investigator, I want to ask the same for a file's **SHA-1**, so that I am
   not forced onto the weakest of the three digests.
8. As a forensic investigator, I want to ask the same for a file's **SHA-256** (NIST's
   dedup key), so that I can use the digest with the strongest collision resistance.
9. As a forensic investigator, I want each **Lookup Result** to state `known` / `unknown`
   for *its* **Algorithm** only, so that "known under MD5" is never conflated with "known
   under SHA-256" for the same file.
10. As a forensic investigator, I want to submit several **Digests** of one **Algorithm** in
    a single **Lookup Session**, so that I can classify a whole corpus in one call.
11. As a forensic investigator, I want each **Lookup Result** to name the **Set**, the
    **Release** date-version, and the applied **Delta releases** that answered it, so that
    my report is fully traceable to the exact dataset it used.
12. As a forensic investigator, I want to submit **Digests** in any letter case and have
    them normalised, so that I don't have to uppercase them by hand first.
13. As a forensic investigator, I want an unparseable **Digest** to come back as a per-item
    `invalid` status inside the results, while the rest of my batch still returns, so that
    one bad value doesn't discard a whole corpus.
14. As a forensic investigator, I want a request for a **Set** I didn't choose, or an
    unsupported **Algorithm**, to be rejected explicitly at the request level, so that I
    know I asked the wrong thing rather than getting a misleading `unknown`.
15. As a forensic investigator, I want to confirm via `/health` which **Release** is loaded
    before I trust the answers I get from it.
16. As a security reviewer of the service, I want every **Lookup Session** to produce an
    **Audit Entry** (timestamp, caller identifier, **Algorithm**, each digest and its
    status, and the **Release** + deltas that answered), so that an open, unauthenticated
    interface remains forensically accountable.
17. As a security reviewer, I want the **Audit Trail** to be append-only and durable, so
    that a record of "what was ever asked" cannot be quietly lost.
18. As a maintainer, I want the service to depend only on current, supported tooling, so
    that I don't maintain it against end-of-life and abandoned components.
19. As a maintainer, I want the test job to run in CI, so that a future change that
    breaks the lookup contract is caught automatically.
20. As a maintainer, I want the retired `nsrlsvr` server, its socket protocol, and its
    build inputs gone from the project, so that no one wires the service back to a
    component NIST is moving away from.
21. As a downstream integrator, I want the response shape to be explicit and versioned
    enough that I can code against the **Lookup Result** fields with confidence.
22. As an operator, I want ingestion to be a one-time mount (never a build or CI step),
    so that my pipelines don't try to move a multi-gigabyte dataset through them.
23. As a forensic investigator, I want a **SHA-256** that NIST deduplicates across many
    files to still resolve to a single `known` answer, so that deduplication on the server
    side doesn't hide a match.
24. As a maintainer, I want the per-Algorithm **hash→known index** rebuilt whenever a
    **Delta release** is applied, so that lookup stays fast and correct across updates.
25. As an operator, I want a clear error if the **Hash Set** is not yet provisioned,
    rather than a service that silently answers against nothing.

## Implementation Decisions

**Architecture (respects ADR-0001, ADR-0003, ADR-0004).**

- The service is a single WSGI application (the current server role) that owns: an HTTP
  layer, a **lookup** module, the **Hash Set** access, and the **Audit Trail**. The
  `nsrlsvr` process and its socket protocol are removed entirely; nothing talks the old
  protocol.
- The **Hash Set** is NIST's **Minimal** **Set** as a SQLite database, mounted **read-only**
  from a provisioned volume. The **Set** is the **Modern** **Set**.
- Ingest is *not* part of the request path. Provisioning produces a queryable **Hash Set**
  plus an identified provenance record (the current **Release** date-version and the list
  of applied **Delta releases**).

**Data model / ingest (respects ADR-0003, ADR-0001).**

- A **provisioning** step takes the NIST **Minimal** archive, applies the current full
  **Release**, then applies the subsequent **Delta release(s)**, yielding one SQLite
  database plus a recorded provenance identity.
- The **hash→known index** is a derived artifact built at ingest — one index per supported
  **Algorithm** (MD5, SHA-1, SHA-256) — because V3 stores digests **UPPERCASE** with no
  standalone hash index, so a raw hash predicate over the full table is a full scan. It is
  rebuilt whenever a **Delta release** is applied.
- The **Set** is **Modern**. The Legacy/Android/iOS **Sets** are out of scope (see
  Out of Scope).
- **CRC-32** is physically present in every V3 row but is *not* a supported lookup
  **Algorithm**; the index and the API accept only MD5, SHA-1, SHA-256.

**API contract (respects ADR-0002).**

- Endpoint: `POST /check`. Body names one **Algorithm** and one **Digest** or a list of
  **Digests** of that same **Algorithm**. One request = one **Algorithm** — no mixing of
  digest types within a request; a caller with mixed data issues separate requests.
- Normalisation: input **Digests** are accepted in any case and normalised to UPPERCASE
  before lookup (V3 stores uppercase; this preserves the old `/check` tolerance).
- **Response — per item**, one **Lookup Result** per submitted **Digest**:

  ```
  {
    "results": [
      {
        "digest": "AD7B9C14...",            // echo, uppercased
        "algorithm": "sha256",             // one of md5 | sha1 | sha256
        "status": "known",                // known | unknown | invalid
        "dataset": {
          "set": "modern",
          "release": "2026.03.1",
          "deltas": ["2026.06.1"]
        }
      }
    ]
  }
  ```

  The schema above is the authoritative shape the tests and the response build from. It came
  from the domain model (`Lookup Result` in `CONTEXT.md` + ADR-0002), not a prototype, but
  is inlined here because the field layout *is* the contract.
- **Status vocabulary.** `known` / `unknown` / `invalid` (the `Invalid` term — a digest
  that isn't well-formed for its declared **Algorithm** — is distinct from `unknown`, which
  was checked and absent).
- **Error/status semantics (locked).** A structurally well-formed request returns **HTTP
  200** even when some **Digests** are unparseable; each unparseable digest is a per-item
  `invalid` in the `results` list, so a batch never fails wholesale. A request naming an
  unsupported **Algorithm**, or a structurally malformed body, is a request-level
  rejection (**4xx**, no `results` list). Unsupported **Set** requests are likewise a
  request-level rejection.
- **`/health`** returns the currently loaded **Release** + applied **Delta releases** (and
  a ready flag), so callers can confirm provenance and liveness before trusting answers.
- **Access model (respects ADR-0004).** The interface is **public** — no authentication.
  There is no auth layer to add here; "add auth" is a tracked, unblocked follow-up, not
  part of this spec.

**Audit Trail (respects ADR-0004).**

- An **Audit Entry** is recorded for every completed **Lookup Session**: timestamp, a
  caller identifier (a fixed service id for now; a caller-supplied identity is a future
  refinement), the **Algorithm**, each **Digest** with its per-item status, and the
  **Release** + applied **Delta releases** that answered.
- The **Audit Trail** is durable and append-only. Nothing in this spec attempts to make it
  tamper-evident beyond durability + append-only; that hardening is out of scope.
- A **Lookup Session** that is rejected at the request level (bad **Algorithm** / malformed
  body) is *not* a successful lookup and produces no **Lookup Result** list, but the
  rejection is still logged as an **Audit Entry** (a forensic record of a bad request is
  worth keeping).

**Hash Set unavailability.**

- If the **Hash Set** is not yet provisioned when the service starts, the service fails to
  start / reports not-ready on `/health` rather than answering against an empty set. A
  `known` answer must never come from "nothing loaded".

**Modern stack (respects the stack decision).**

- Runtime and server: the current Python line (the EOL runtime is replaced), a current WSGI
  server, and the current web-framework major. The server runs the single WSGI app.
- Test tooling: the current `pytest` plus a coverage plugin; the abandoned legacy test
  runner and its coverage plugin are removed. The logging shim that replaced a legacy
  paste-based component is replaced by the standard library.
- Build images are tagged by minor version, not by an EOL one; the obsolete top-level
  compose `version` field is dropped.
- A CI **test job** runs the unit + integration suites; the workflow set is currently
  static-scans only, so this is first-class new.

## Testing Decisions

**What a good test is here.** Tests assert **external behaviour** at a seam, not the SQL or
the index internals. The behaviour under test is the *mapping from a request (Digest,
Algorithm, Hash Set) to a Lookup Result and its side effects (an Audit Entry)*. A test must
not reach into the index-build code or the SQLite queries directly; it reaches in only
through the two seams below.

**The two seams (confirmed with the user):**

- **Seam 1 — the API boundary (existing, adapted).** The highest seam. Drive the new
  `POST /check` and `/health` through the application's WSGI/HTTP test client — the same
  seam both existing test files use, with the live-`nsrlsvr` dependency removed. At this
  boundary assert: per-item `known`/`unknown`/`invalid`; 200-with-per-item-`invalid` vs
  4xx-on-bad-**Algorithm**/malformed-body; full provenance present in the `dataset` block;
  and that, after a successful **Lookup Session**, an **Audit Entry** for it exists. The
  **Audit Trail** is black-boxed *through* this seam — it is verified by observing its
  effect (the entry was produced), not by a dedicated audit seam; the store's internals are
  implementation.
- **Seam 2 — the lookup module (new; the only added seam).** Exposed as a single public
  function of the form `look_up(hash_set, digests, algorithm) -> [Lookup Result]`, queried
  against a tiny fixture **Hash Set** (a small SQLite **Set** with a handful of known and
  unknown digests). This is the highest point at which data-driven `known`/`unknown`
  behaviour is cheaply assertable without standing up HTTP against multi-gigabyte data, and
  the point at which *which* **Release** + **Delta releases** answered is independently
  assertable. It is used for the MD5/SHA-1/SHA-256 equivalence and SHA-256-dedup cases that
  are awkward to reach through the API against real data.
- **Not a behavioural seam:** the **provision** / **delta-apply** / **index-build** side is
  I/O-bound on multi-GB real data and is verified by a build-time **smoke check** ("a small
  minimal-style DB + a sample delta yields a queryable, indexed **Hash Set** with expected
  known/unknown"), *not* by a unit- or behaviour-level test.

**Modules tested:** the API behaviour (at Seam 1) and the **lookup** module (at Seam 2).
The audit trail is exercised incidentally as an effect asserted at Seam 1. Provisioning and
index build have only the smoke check.

**Prior art.** `api/tests/unit/test_ping.py` (a one-line client GET + status assert) and
`api/tests/integration/test_hash_lookup.py` (client GETs asserting the `result` field and
its `true`/`false`/`invalid hash format` values across known, unknown, lower-case,
upper-case, and two malformed-input cases). The new Seam-1 tests are the modern, multi-
algorithm, provenance-carrying successors to that integration file; the known/unknown
fixtures already have a home (`api/tests/hashes.txt`, currently holding one known MD5).
The suite is migrated to `pytest` (+ a coverage plugin) as part of the stack work, and a CI
job is added.

## Out of Scope

- **Auth / caller identity.** The interface is intentionally public. No token, key, or
  OAuth. A caller-supplied identity (versus the current fixed service id) in the **Audit
  Entry** is a future refinement, not part of this spec.
- **The Legacy, Android, and iOS **Sets.** Only the **Modern** **Set** is in scope. (The
  Minimal **Set** and the delta model are the mechanism; picking other **Sets** is later.)
- **Tamper-evident audit storage.** The **Audit Trail** is durable and append-only;
  cryptographic tamper-evidence (hash-chaining, WORM storage) is not in this spec.
- **CRC-32 lookup.** The column exists in V3 but is not a supported **Algorithm**.
- **Mixing digest types within one request.** One **Algorithm** per **Lookup Session**.
- **Provisioning automation's full production story** (the multi-GB download transport,
  scheduling of delta application, storage of the volume) — these are operational; this
  spec fixes the contract the service consumes, not the deployment pipeline.
- **The old response shape.** Consumers must migrate; the MD5-only `GET /check/<hash>` and
  its `{result: "true|false|invalid hash format"}` are removed.

## Further Notes

- **Provenance is the load-bearing idea.** Because the interface is open, every answer and
  every request is only trustworthy through its recorded **Release** + **Delta** identity.
  Any new field on the **Lookup Result** should be judged by "does this help a forensic
  consumer know exactly what answered".
- **The dataset is a moving target.** NIST publishes quarterly — a full **Release** in
  March, **Delta releases** in June, September, December — and a current public download was
  confirmed live during triage, but the *exact published object path is not pinned by this
  spec*; provisioning must resolve "the current release" at ingest time and record what it
  found. The spec fixes the *shape* of what provisioning yields, not the URL.
- **The on-disk V3 layout is not fully confirmed.** Schema is known from NIST's V3 doc
  (SQLite; a metadata table with the per-file digests; uppercase digests; no standalone
  hash index — which is *why* the per-Algorithm index exists). Full on-disk confirmation is
  deferred to a dedicated task (triage ticket `01`) at implementation time and is gated
  behind "do not unpack a multi-gigabyte release in a design session".
- **Vocabulary.** This spec uses the terms of `CONTEXT.md` (RDS, Set, Minimal set, Release,
  Delta release, Hash Set, Digest, Algorithm, Known/Unknown, Invalid, Lookup Session, Lookup
  Result, Audit Entry, Audit Trail) and respects ADR-0001..0004. Any drift there should be
  reconciled with the domain model, not silently absorbed.
- **Relationship to tickets.** `.scratch/triage/issues/01..08` are the delivery tickets for
  this spec; this doc is the behaviour they must satisfy. Ticket `01` (learn the V3 layout)
  and ticket `08` (audit trail) gate / extend the contracts above respectively.
