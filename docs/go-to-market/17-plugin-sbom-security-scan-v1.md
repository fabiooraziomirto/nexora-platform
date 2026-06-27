# Plugin SBOM and Security Scan v1

## Status
Implemented in plugin-service and validated with live API smoke tests.

## Objective
Add a deploy-time security gate for function plugins based on:
- SBOM presence
- vulnerability scan verdict

## New API
- `POST /api/v2/plugins/{plugin_id}/security/scan`

## Extended Plugin Fields
- `sbom_uri`
- `security_scan_tool`
- `security_scan_status` (`pending|passed|failed`)
- `security_scan_summary`
- `scanned_at`

## Activation Gate
When `module_type=function` and `PLUGIN_SECURITY_SCAN_REQUIRED=true`:
1. `sbom_uri` must be present
2. `security_scan_status` must be `passed`

Otherwise activation is blocked.

## Scan Request Payload (v1)
```json
{
  "scan_tool": "grype",
  "sbom_uri": "s3://sbom/secure-fn-1.0.0.cdx.json",
  "vulnerability_counts": {
    "critical": 0,
    "high": 0,
    "medium": 2,
    "low": 1
  }
}
```

## Verdict Policy (default)
- fail if `critical > 0`
- fail if `high > 0`
- pass otherwise

Configurable via env:
- `PLUGIN_SECURITY_SCAN_REQUIRED` (default `true`)
- `PLUGIN_SECURITY_MAX_CRITICAL` (default `0`)
- `PLUGIN_SECURITY_MAX_HIGH` (default `0`)

## Live Validation Evidence
Runtime: local dev stack (`docker compose --profile dev`).

Validated flow:
1. Activate function without scan -> `400 sbom_uri required before activating a function`
2. Record failed scan (`critical=1`) -> `security_scan_status=failed`
3. Activate after failed scan -> `409 security scan must pass before activating a function`
4. Record passed scan (`critical=0, high=0`) -> `security_scan_status=passed`
5. Activate after passed scan -> `200` and plugin status `active`

## Next Iteration
- Add signed attestation checks (in-toto/cosign).
- Parse scanner-native report formats directly (CycloneDX + Grype/Trivy JSON) instead of only summarized counts.
- Enforce policy in execution-service dispatch as second-line runtime guard.
