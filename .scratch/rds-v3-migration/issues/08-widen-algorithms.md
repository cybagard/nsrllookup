# 08: Widen lookup + API to SHA-1 & SHA-256

**What to build:** all three **Algorithms** become first-class. The per-Algorithm index, the
`look_up` module, and `POST /check` accept **SHA-1** and **SHA-256** alongside **MD5**.
Proves **Known** is a per-**Algorithm** property and that a NIST-deduplicated **SHA-256**
still resolves to a single **Known** answer.

**Blocked by:** 07 (`POST /check` + `/health` for MD5)

**Status:** ready-for-agent

- [ ] The per-Algorithm index is built for **SHA-1** and **SHA-256** as well as **MD5**.
- [ ] `look_up` and `POST /check` accept **SHA-1** and **SHA-256**.
- [ ] A digest **Known** under one **Algorithm** is not reported **Known** under another for
      the same file (**Known** is per-**Algorithm**).
- [ ] A **SHA-256** that NIST deduplicates across many files still resolves to one
      **Known** answer.
- [ ] **CRC-32** remains rejected as a lookup **Algorithm**.

## Comments
