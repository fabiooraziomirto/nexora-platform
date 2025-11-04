# ADR-007: Autenticazione - Keycloak + Keystone Integration

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 necessita di un sistema di autenticazione che:
- Supporti integrazione con OpenStack Keystone (per compatibilità esistente)
- Offra flessibilità con Keycloak (OAuth2/OIDC standard)
- Permetta migrazione graduale da Keystone
- Supporti multi-tenant
- Supporti SSO (Single Sign-On)
- Gestisca OAuth2, OIDC, SAML

## Decision

Utilizzare **Keycloak come autenticazione primaria** con **Keystone come fallback/secondary** per compatibilità.

Architettura:
```
┌─────────────────────────────────────────┐
│         API Gateway (Kong)              │
│  ┌──────────────────────────────────┐  │
│  │  Auth Plugin                     │  │
│  │  - Keycloak (primary)            │  │
│  │  - Keystone (fallback)           │  │
│  └──────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌──────▼──────┐
│  Keycloak   │  │  Keystone   │
│  (Primary)  │  │  (Legacy)   │
└─────────────┘  └─────────────┘
```

## Motivazioni

### Keycloak (Primary)
- ✅ **Standard OAuth2/OIDC**: Compatibilità universale
- ✅ **Multi-tenant**: Supporto nativo realm
- ✅ **Identity Brokering**: Può federare con Keystone
- ✅ **User Federation**: LDAP, Active Directory, etc.
- ✅ **Fine-grained Authorization**: UMA 2.0
- ✅ **Modern UI**: Admin console moderna
- ✅ **Community**: Grande community, attivo sviluppo

### Keystone (Fallback)
- ✅ **Compatibilità OpenStack**: Necessario per integrazioni esistenti
- ✅ **Service Account**: Per service-to-service auth
- ✅ **Migrazione graduale**: Permette transizione senza breaking changes

## Implementazione

### Fase 1: Dual Authentication
- Keycloak come primary
- Keystone come fallback per servizi legacy
- API Gateway gestisce routing

### Fase 2: Keycloak Identity Brokering
- Keycloak federato con Keystone
- Unico punto di autenticazione
- Trasparente per utenti

### Fase 3: Migrazione Completa
- Tutti i servizi su Keycloak
- Keystone mantenuto solo per OpenStack services

## Consequences

### Positive
- ✅ Standard moderni (OAuth2/OIDC)
- ✅ Flessibilità identità (multi-source)
- ✅ Migrazione graduale possibile
- ✅ Better UX (Keycloak UI)
- ✅ Enterprise features (SSO, MFA)

### Negative
- ⚠️ Complessità iniziale (due sistemi)
- ⚠️ Maintenance overhead (due sistemi da gestire)
- ⚠️ Potential confusion (due auth endpoints)

### Mitigation
- Clear documentation su quando usare cosa
- Gradual migration plan
- Deprecation timeline per Keystone

## Alternatives Considered

### Solo Keycloak
- ✅ Semplicità
- ❌ Breaking changes per integrazioni esistenti
- ❌ Perdita compatibilità OpenStack diretta

### Solo Keystone
- ✅ Compatibilità OpenStack
- ❌ Standard meno moderni
- ❌ Meno flessibile per futuro

### Auth0/Okta (SaaS)
- ✅ Managed service
- ❌ Costo mensile
- ❌ Vendor lock-in
- ❌ Meno controllo

## References

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Keystone Documentation](https://docs.openstack.org/keystone/)
- [Keycloak Identity Brokering](https://www.keycloak.org/docs/latest/server_admin/#_identity_broker)


