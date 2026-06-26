# MVP Release Checklist

Before tagging a release candidate, verify every item below.

## Code Quality
- [ ] All unit tests pass (`pytest` per service)
- [ ] `scripts/test-all.sh` exits 0 (structure + syntax + compose smoke)
- [ ] `scripts/contract-tests-api.py` passes positive + negative checks
- [ ] `scripts/nexora-device-emulator-e2e.sh` completes the full lifecycle

## Security
- [ ] Bootstrap tokens are not hard-coded in production compose
- [ ] AUTH_ENABLED=true tested with a real Keycloak realm
- [ ] No secrets committed in repository

## Documentation
- [ ] `docs/deployment/nexora-parity-matrix.md` reviewed
- [ ] `docs/deployment/execution-pipeline-runbook.md` reviewed
- [ ] ADR for execution pipeline approved

## Operations
- [ ] Prometheus rules loaded (`infrastructure/sre/prometheus-rules-nxr.yaml`)
- [ ] Docker images tagged with semver
- [ ] Compose smoke test on a clean machine
