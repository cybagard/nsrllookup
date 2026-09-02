# 08: Widen lookup + API to SHA-1 & SHA-256

**What to build:** all three **Algorithms** become first-class. The per-Algorithm index, the
`look_up` module, and `POST /check` accept **SHA-1** and **SHA-256** alongside **MD5**.
Proves **Known** is a per-**Algorithm** property and that a NIST-deduplicated **SHA-256**
still resolves to a single **Known** answer.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** resolved

- [x] The per-Algorithm index is built for **SHA-1** and **SHA-256** as well as **MD5**.
- [x] `look_up` and `POST /check` accept **SHA-1** and **SHA-256**.
- [x] A digest **Known** under one **Algorithm** is not reported **Known** under another for
       the same file (**Known** is per-**Algorithm**).
- [x] A **SHA-256** that NIST deduplicates across many files still resolves to one
        **Known** answer.
- [x] **CRC-32** remains rejected as a lookup **Algorithm**.

## Comments

The data/lookup/index layers were already algorithm-agnostic (iterating
`SUPPORTED_ALGORITHMS`); ticket 08 adds the assertions. `api/tests/integration/
test_widen_algorithms.py` proves the index is built for all three algorithms,
SHA-1 & SHA-256 are accepted by `POST /check` in any case, a value **Known**
under MD5 is never reported **Known** under SHA-256, a NIST-deduplicated
SHA-256 shared across two rows resolves to a single **Known**, and CRC-32 is a
400. (Fixture SHA-256 corrected to a 64-char value.)
