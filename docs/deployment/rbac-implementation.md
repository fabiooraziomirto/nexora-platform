# RBAC System Documentation

## Overview

Stack4Things v2.0 implements a comprehensive RBAC (Role-Based Access Control) system compatible with OpenStack standards and enhanced with custom roles.

## Architecture

```
┌─────────────────────────────────────────┐
│         Application Services            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│      RBAC Service (Policy Engine)       │
│  - Policy Evaluation                     │
│  - Policy Cache                          │
│  - Audit Logging                         │
└──────────────┬──────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
┌───────▼──────┐  ┌──▼──────────────┐
│   Keycloak    │  │   Keystone     │
│  (Roles)      │  │   (Roles)      │
└───────────────┘  └─────────────────┘
```

## Components

### 1. Roles

#### OpenStack Standard Roles

- **admin**: Full administrative access
- **member**: Standard user access
- **reader**: Read-only access
- **service**: Service account access

#### Stack4Things Custom Roles

- **device-admin**: Device management administrator
- **fleet-manager**: Fleet management role
- **network-admin**: Network management role
- **plugin-developer**: Plugin development role
- **execution-operator**: Execution management role
- **auditor**: Audit and read-only access

### 2. Policy Engine

- **oslo.policy style**: Compatible with OpenStack policy evaluation
- **Rule-based**: Flexible policy rules
- **Context-aware**: Supports user, project, resource context

### 3. Policy Caching

- **Redis-backed**: Fast policy evaluation caching
- **TTL**: 1 hour default
- **Invalidation**: Automatic on role/policy changes

### 4. Audit Logging

- **Comprehensive**: Logs all access attempts
- **JSON format**: Structured audit logs
- **Retention**: 90 days
- **Fields**: User, action, resource, result, timestamp

## Quick Setup

```bash
# Complete RBAC setup
./scripts/kubernetes/rbac/setup-rbac.sh

# Integrate with Keycloak
./scripts/kubernetes/rbac/integrate-keycloak.sh

# Integrate with Keystone
./scripts/kubernetes/rbac/integrate-keystone.sh

# Setup audit logging
./scripts/kubernetes/rbac/setup-audit.sh
```

## Policy Rules

### Policy Format

Policies use oslo.policy style syntax:

```json
{
  "devices:create": "rule:admin_or_creator",
  "devices:read": "rule:admin_or_owner or role:reader",
  "devices:read:own": "rule:admin_or_creator",
  "devices:update": "rule:admin_or_owner",
  "devices:delete": "rule:admin_or_owner"
}
```

### Rule Types

- **role:admin**: User has admin role
- **project_id:%(project_id)s**: User belongs to project
- **user_id:%(user_id)s**: User owns resource
- **rule:admin_or_owner**: Reference to another rule

## Usage Examples

### Policy Evaluation API

```python
import requests

# Authorize action
response = requests.post(
    "http://rbac-service.stack4things.svc.cluster.local:8000/api/v2/rbac/authorize",
    json={
        "user_id": "user-123",
        "user_name": "john.doe",
        "roles": ["member", "fleet-manager"],
        "action": "create",
        "resource_type": "fleet",
        "project_id": "project-456"
    }
)

result = response.json()
if result["allowed"]:
    # Proceed with action
    pass
else:
    # Deny access
    raise PermissionError(result["reason"])
```

### Service Integration

```python
from rbac_service.client import RBACClient

rbac = RBACClient(
    endpoint="http://rbac-service.stack4things.svc.cluster.local:8000"
)

# Check authorization
allowed = await rbac.authorize(
    user_id="user-123",
    roles=["member"],
    action="read",
    resource_type="device",
    resource_id="device-456"
)
```

## Keycloak Integration

Roles are synchronized from Keycloak:

```bash
# Roles are automatically mapped from Keycloak
# User roles in Keycloak → RBAC permissions
```

## Keystone Integration

Roles are synchronized from Keystone:

```bash
# Roles are automatically mapped from Keystone
# User roles in Keystone → RBAC permissions
```

## Audit Logging

### View Audit Logs

```bash
# View audit logs
kubectl logs -n stack4things -l app=rbac-service | grep audit

# Query audit logs via API
curl http://rbac-service.stack4things.svc.cluster.local:8000/api/v2/rbac/audit
```

### Audit Log Format

```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "user_id": "user-123",
  "user_name": "john.doe",
  "roles": ["member"],
  "action": "read",
  "resource_type": "device",
  "resource_id": "device-456",
  "result": "allowed",
  "ip_address": "10.0.0.1",
  "user_agent": "Mozilla/5.0..."
}
```

## Troubleshooting

### Policy Not Evaluating Correctly

```bash
# Check policy configuration
kubectl get configmap policy-config -n stack4things -o yaml

# Check RBAC service logs
kubectl logs -n stack4things -l app=rbac-service
```

### Role Not Found

```bash
# Check roles in Keycloak
kubectl exec -it keycloak-0 -n stack4things-auth -- \
  curl http://localhost:8080/admin/realms/stack4things/roles

# Check role mappings
kubectl get configmap keycloak-role-mappings -n stack4things-auth -o yaml
```

## Production Considerations

1. **Performance**: Use policy caching for high-traffic scenarios
2. **Security**: Regularly audit policy rules and role assignments
3. **Monitoring**: Monitor policy evaluation metrics
4. **Compliance**: Ensure audit logs meet compliance requirements
5. **Scalability**: Scale RBAC service based on load

## References

- [OpenStack Policy Guide](https://docs.openstack.org/oslo.policy/latest/)
- [Keycloak Roles](https://www.keycloak.org/docs/latest/server_admin/#_roles)
- [Keystone Roles](https://docs.openstack.org/keystone/latest/admin/service-api.html#roles)
