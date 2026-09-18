# 05: Resync the stale triage tracker

**What to build:** the `.scratch/triage/issues/*` files all still carry `Status: open` even
though tickets 01–09 of that effort are committed (see `git log`); a new agent or human would
misread the project as entirely unstarted. This housekeeping slice resyncs those `Status:`
lines to `resolved` (or retires the stale `triage` effort dir) so the tracker reflects
reality. It is a tracker-only change, independent of the production-functional code work.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] Every `.scratch/triage/issues/*` `Status:` line reflects the committed state
         (01–08 resolved), or the stale effort dir is retired in favour of the live spec and
        tickets.
- [x] The resync matches `git log` (no ticket shown as open that is in fact committed).
- [x] No code, test, or ADR is changed by this ticket.

## Comments

Resynced all 8 `.scratch/triage/issues/*` from `Status: open` to `resolved`, each annotated
with the commit(s) that landed the work (01 `3ba267c`; 02 `5671832`/`3556c3e`; 03 `36c0350`/
`0af05af`; 04 `74cf77d`/`2a5b904`; 05 `74cf77d`; 06 `74cf77d`; 07 `2a5b904`; 08 `2a5b904`).
Tracker-only: `git status` shows the 8 issue files modified and nothing under `api/`, `docs/`,
or `tests/` touched. (The 8 files are the full triage set; the ticket's "01–09" counts the
superseding effort's 09 housekeeping item, already tracked under `rds-v3-live/09`.)
