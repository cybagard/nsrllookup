# 05: Resync the stale triage tracker

**What to build:** the `.scratch/triage/issues/*` files all still carry `Status: open` even
though tickets 01–09 of that effort are committed (see `git log`); a new agent or human would
misread the project as entirely unstarted. This housekeeping slice resyncs those `Status:`
lines to `resolved` (or retires the stale `triage` effort dir) so the tracker reflects
reality. It is a tracker-only change, independent of the production-functional code work.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Every `.scratch/triage/issues/*` `Status:` line reflects the committed state
        (01–09 resolved), or the stale effort dir is retired in favour of the live spec and
        tickets.
- [ ] The resync matches `git log` (no ticket shown as open that is in fact committed).
- [ ] No code, test, or ADR is changed by this ticket.
