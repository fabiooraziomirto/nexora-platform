# ADR-0003 — Modular Service Structure Standard

**Status**: Accepted  
**Date**: 2026-06-25  
**Scope**: All FastAPI microservices in Nexora platform

---

## Context

All 7 core services started as flat single-file implementations (`main.py`) with
all config, models, metrics, events, and route handlers inlined. This made
cross-cutting concerns (auth, Kafka, observability) copy-pasted across files and
prevented unit testing individual layers in isolation.

---

## Decision

All services adopt a `src/<service_name>/` Python package layout with the
following subpackage structure:

```
src/<service_name>/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── config.py       — env-var constants (read once at import time)
│   ├── database.py     — SQLAlchemy Base, engine, SessionLocal
│   ├── metrics.py      — Prometheus counters/histograms/gauges
│   └── events.py       — Kafka producer + publish_event (where applicable)
├── models/
│   ├── __init__.py
│   └── <model>.py      — ORM model class + domain helpers
└── api/
    ├── __init__.py
    └── <resource>.py   — APIRouter with route handlers (where test constraints allow)
```

The service entrypoint remains at the **service root** as `main.py`, which:
1. Inserts `src/` into `sys.path` so the package is importable without `PYTHONPATH`.
2. Imports from `<service_name>.core.*` and `<service_name>.models.*`.
3. Hosts the FastAPI `app`, all middleware, lifecycle hooks, and route definitions.

### Constraint: test-coupled routes

Services whose tests use `monkeypatch.setattr("main.X")` or `import main; main.X = ...`
(execution-service, fleet-service, dns-service, network-service, webservice-service)
must keep route handlers and the monkeypatched variables in root `main.py`. Moving
them to `api/` would break the monkeypatch coupling because Python resolves module
globals from the module where the function was defined, not where it was imported.

Plugin-service is an exception: its tests import from `plugin_service.main`, allowing
a full separation with routes in `api/plugins.py` and a thin `main.py` coordinator.

---

## Commit references

| Service | Commit |
|---|---|
| execution-service (pilot) | 365c311 |
| plugin-service | 69c59c9 |
| fleet-service | 7d129d8 |
| dns-service | 379431c |
| network-service | 74e41ab |
| webservice-service | 42de939 |
| nexora-edge | 16c0e79 |

---

## Consequences

**Positive**
- Config, database, metrics, and event publishing are independently testable.
- No more copy-paste of the same boilerplate across flat files.
- Clear import boundaries make dependency direction explicit.
- Docker `COPY src ./src` + `PYTHONPATH=/app/src` pattern is consistent.

**Negative**
- Existing tests that import `from main import X` must remain unchanged and the
  test-coupling constraint prevents moving routes to `api/` for those services.
  A follow-up refactor could fix this by updating tests to import from the package.
- Root `main.py` is still non-trivial for most services (contains routes + startup).
  Full thin-coordinator migration requires test updates.

---

## Notes

nexora-edge has **0 unit tests**. Its only behavioral verification is
`scripts/nexora-device-emulator-e2e.sh` against a running stack. The migration was validated
by confirming the module imports without error; runtime validation is deferred to
the next stack-up opportunity.
