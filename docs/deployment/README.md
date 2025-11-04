# Deployment Guides

## Quick Links

- [Kubernetes Setup](./kubernetes-setup.md) - Setup k3d cluster and infrastructure
- [Monitoring Stack](./monitoring-setup.md) - Prometheus, Grafana, Tempo, Loki
- [Database Setup](./database-setup.md) - MySQL/MariaDB HA, ProxySQL, Backups
- [Alembic MySQL Guide](./alembic-mysql-guide.md) - Database migrations
- [Keycloak Integration](./keycloak-integration.md) - Authentication setup
- [Crossplane Guide](./crossplane-guide.md) - Infrastructure provisioning
- [OpenStack Compatibility](./openstack-compatibility.md) - OpenStack integration
- [Multi-Architecture Support](./multi-arch-support.md) - ARM64 and AMD64 support

## Deployment Order

1. **Kubernetes Cluster**: Setup k3d cluster
2. **Infrastructure**: Namespaces, RBAC, Ingress, Cert-Manager
3. **Monitoring**: Prometheus, Grafana, Tempo, Loki
4. **Database**: MySQL/MariaDB HA, ProxySQL, Backups
5. **Authentication**: Keycloak + Keystone
6. **Services**: Deploy microservices
7. **API Gateway**: Kong configuration

# Deployment Guides

## Quick Links

- [Kubernetes Setup](./kubernetes-setup.md) - Setup k3d cluster and infrastructure
- [Monitoring Stack](./monitoring-setup.md) - Prometheus, Grafana, Tempo, Loki
- [Database Setup](./database-setup.md) - MySQL/MariaDB HA, ProxySQL, Backups
- [Alembic MySQL Guide](./alembic-mysql-guide.md) - Database migrations
- [Redis Setup](./redis-setup.md) - Redis Cluster HA
- [Kafka Setup](./kafka-setup.md) - Kafka Cluster and Topics
- [Secret Management](./secret-management.md) - Kubernetes Secrets and Vault
- [Keycloak Integration](./keycloak-authentication.md) - Authentication setup
- [Crossplane Guide](./crossplane-guide.md) - Infrastructure provisioning
- [RBAC Implementation](./rbac-implementation.md) - Role-Based Access Control
- [OpenStack Compatibility](./openstack-compatibility.md) - OpenStack integration
- [Multi-Architecture Support](./multi-arch-support.md) - ARM64 and AMD64 support

## Deployment Order

1. **Kubernetes Cluster**: Setup k3d cluster
2. **Infrastructure**: Namespaces, RBAC, Ingress, Cert-Manager
3. **Monitoring**: Prometheus, Grafana, Tempo, Loki
4. **Database**: MySQL/MariaDB HA, ProxySQL, Backups
5. **Cache & Message Broker**: Redis Cluster, Kafka
6. **Secret Management**: Kubernetes Secrets or Vault
7. **Authentication**: Keycloak + Keystone
8. **Services**: Deploy microservices
9. **API Gateway**: Kong configuration

## Architecture

- **Multi-Architecture**: Supports AMD64 and ARM64
- **Cloud-Native**: Designed for Kubernetes
- **Observable**: Full monitoring and tracing
- **Secure**: Authentication and RBAC
- **High Availability**: MySQL HA, Redis Sentinel, Kafka replication
- **Event-Driven**: Kafka for event streaming

## Keycloak Deployment
- Namespace: `keycloak`
- Service: `keycloak.keycloak:8080`
- Admin Console: `http://keycloak.keycloak:8080/admin`
- Realm: `stack4things`

## Keystone Integration
- Identity Broker: Configured in Keycloak Admin Console
- Fallback: Automatic via Kong plugin

## Kong Configuration
- Primary Auth: Keycloak OIDC plugin
- Fallback Auth: Keystone plugin
- Routing: Keycloak first, Keystone fallback

## Database
- Type: MySQL/MariaDB 10.11+
- HA: Primary + 2 read replicas
- Connection Pooling: ProxySQL
- Backups: Daily automated backups (7-day retention)
- Compatible: OpenStack standard database
- Option: Shared cluster with OpenStack

## OpenStack Compatibility
- Target Version: 2024.1 (Antelope) or later
- Components: Keystone, Neutron, Designate
- Full API compatibility maintained


