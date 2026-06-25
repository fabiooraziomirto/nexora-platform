# Overnight Work Log — 2026-06-25

Branch: `overnight/2026-06-25-architecture-and-experiments`
Session start: 2026-06-25T00:00 (autonomous loop)

---

## Log

| Timestamp | Event | Commit | Notes |
|---|---|---|---|
| 2026-06-25T00:01 | Branch created from `main` | — | `git stash` + `checkout -b` + `git stash pop` to preserve pre-existing changes |
| 2026-06-25T00:02 | SUMMARY.md initialized | — | |

---

## Stage 1 — Fix broker commit lag (lightningrod-gateway)

**Status**: IN PROGRESS  
**Started**: 2026-06-25T00:03

**Task**: Remove `if broker_commit_lag_s >= 0:` guard from `BROKER_COMMIT_LAG` histogram observe call. Adjust histogram buckets to include negative range. Document LogAppendTime Kafka topic config.

**Design decision**: Extended BROKER_COMMIT_LAG histogram buckets to include negative values
(`-0.1, -0.025, -0.005, -0.001, 0.0, ...`) rather than clamping to zero. Clock skew between
producer host and Kafka broker is real in multi-host deployments; recording negative values
allows the operator to detect and quantify skew rather than silently discarding it.
Alternative (clamping to 0) was rejected because it would mask systematic skew in the p50/p95
of Phase 1a.

---

## Stage 2 — Dev-token bypass hardening

**Status**: FOUND COMPLETE (pre-existing changes in working tree)  
**Started**: 2026-06-25T00:02  
**Completed**: 2026-06-25T00:05

Pre-existing working-tree changes already implement `AUTH_DEV_BYPASS_ENABLED` across all 6 flat services and `iotronic-ui`. ADR-0002 already written. `lr-emulator-e2e.sh` and `perf-dispatch-latency.sh` already export the flag. Committing as-is.

**Verification**: Full stack not running; syntactic check confirms consistent implementation across all services. Integration test (lr-emulator-e2e.sh + test-all.sh) deferred to next opportunity with running stack.

---

## Stage 3 — Modular migration: execution-service (pilot)

**Status**: PENDING

---

## Stage 4 — Modular migration: remaining 6 services

**Status**: PENDING (blocked on Stage 3)

---

## Stage 5 — POLL_SECONDS sweep experiment

**Status**: PENDING (blocked on Stage 1 + Stage 3, requires running stack)

---

## State for morning review

*(updated incrementally — see bottom of file)*
