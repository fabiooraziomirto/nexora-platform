# ADR-009: RBAC - Role-Based Access Control

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 necessita di un sistema di controllo accessi granulare che:
- Supporti multi-tenant
- Permetta controllo per risorsa (device, fleet, plugin)
- Sia compatibile con OpenStack Keystone roles
- Supporti custom roles per Stack4Things
- Permetta delegation e sharing resources

## Decision

Implementare **RBAC multi-layer** con:
1. **Keystone Roles** (base) - per autenticazione OpenStack
2. **Keycloak Roles** (extended) - per features avanzate
3. **Policy Engine** (fine-grained) - per controllo granulare

Architettura:
```
┌─────────────────────────────────────────┐
│   API Request                           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   API Gateway (Kong)                    │
│   - Extract user context                │
│   - Pass to services                    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│   Policy Engine                          │
│   - Check Keystone roles                │
│   - Check Keycloak roles                │
│   - Evaluate policies                   │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌──────▼──────┐
│  Keystone   │  │  Keycloak   │
│  (Roles)    │  │  (Roles)     │
└─────────────┘  └─────────────┘
```

## Motivazioni

### Multi-Layer Approach
- ✅ **Keystone Roles**: Compatibilità OpenStack standard
- ✅ **Keycloak Roles**: Features avanzate (hierarchical, composite)
- ✅ **Policy Engine**: Controllo granulare per risorsa

### Granularità
- ✅ Control per device individuale
- ✅ Control per fleet
- ✅ Control per plugin
- ✅ Control per operazione (read, write, execute)

### Multi-Tenant
- ✅ Project isolation
- ✅ Resource sharing controllato
- ✅ Delegation support

## Ruoli Predefiniti

### OpenStack Standard Roles
- `admin` - Full access (OpenStack standard)
- `member` - Project member (OpenStack standard)
- `reader` - Read-only (OpenStack standard)

### Stack4Things Custom Roles
- `admin_iot_project` - Full control su progetto IoT
- `manager_iot_project` - Manage devices, fleets, plugins
- `user_iot` - Use devices, execute plugins
- `fleet_manager` - Manage specific fleet
- `device_operator` - Operate specific device
- `plugin_developer` - Create/manage plugins

## Policy Model

### Policy Structure
```yaml
# policy.json
{
  "iot:device:get": "role:user_iot",
  "iot:device:create": "role:manager_iot_project",
  "iot:device:update": "role:manager_iot_project or project:owner",
  "iot:device:delete": "role:admin_iot_project",
  "iot:fleet:manage": "role:fleet_manager",
  "iot:plugin:create": "role:plugin_developer",
  "iot:plugin:execute": "role:user_iot"
}
```

### Resource-Level Policies
```yaml
# Per device specifico
device:abc-123:
  read: [user:alice, fleet:prod-fleet]
  write: [user:alice]
  execute: [user:alice, user:bob]

# Per fleet
fleet:prod-fleet:
  manage: [user:alice, role:fleet_manager]
  members: [user:alice, user:bob, user:charlie]
```

## Implementation

### Policy Engine
- Utilizzare `oslo.policy` (OpenStack standard)
- Custom policy evaluator per resource-level
- Caching per performance

### API Integration
- Middleware per policy enforcement
- Context propagation
- Audit logging

### UI Integration
- Role management UI
- Policy visualization
- Permission checker

## Consequences

### Positive
- ✅ Fine-grained access control
- ✅ Multi-tenant support
- ✅ OpenStack compatibility
- ✅ Flexible permission model

### Negative
- ⚠️ Complessità gestione policy
- ⚠️ Performance overhead (mitigato con caching)

### Mitigation
- Policy caching
- Async policy evaluation dove possibile
- Clear documentation

## Alternatives Considered

### Solo Keystone Roles
- ✅ Simplicity
- ❌ Limiti nella granularità
- ❌ Meno flessibile

### Solo Keycloak Roles
- ✅ Features avanzate
- ❌ Perdita compatibilità OpenStack

### ABAC (Attribute-Based)
- ✅ Molto flessibile
- ❌ Complessità alta
- ❌ Overhead performance

## References

- [OpenStack Policy Guide](https://docs.openstack.org/oslo.policy/latest/)
- [Keycloak Authorization Services](https://www.keycloak.org/docs/latest/authorization_services/)
- [RBAC Best Practices](https://www.owasp.org/index.php/RBAC)


