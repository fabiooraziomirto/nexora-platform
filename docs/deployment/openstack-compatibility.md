# OpenStack Compatibility Guide - Stack4Things v2.0

## 🎯 Overview

Stack4Things v2.0 è progettato per essere **completamente compatibile** con l'ultima versione di OpenStack, garantendo integrazione seamless e supporto completo.

## 📊 Compatibilità OpenStack

### Versioni Supportate

| OpenStack Release | Status | Support Level | Notes |
|-------------------|--------|---------------|-------|
| **2024.1 (Antelope)** | ✅ Full Support | Production Ready | Recommended |
| **2023.2 (Zed)** | ✅ Full Support | Production Ready | Stable |
| **2023.1 (Yoga)** | ✅ Full Support | Production Ready | Stable |
| **2022.2 (Wallaby)** | ⚠️ Limited | Maintenance | Deprecated |
| **2022.1 (Victoria)** | ❌ Not Supported | - | EOL |

**Target Version**: OpenStack 2024.1 (Antelope) o superiore

### Componenti OpenStack Integrati

| Component | Version | Integration Method | Status |
|-----------|---------|-------------------|--------|
| **Keystone** | Latest | Identity Provider | ✅ Full |
| **Neutron** | Latest | Network API | ✅ Full |
| **Designate** | Latest | DNS API | ✅ Full |
| **Glance** | Latest | Image API (optional) | ✅ Supported |
| **Nova** | Latest | Compute API (optional) | ✅ Supported |

## 🔧 Configuration per OpenStack

### 1. Keystone Integration

```yaml
# config/openstack/keystone.yaml
keystone:
  version: "2024.1"  # Antelope
  auth_url: "http://keystone:5000/v3"
  auth_type: "password"
  project_domain_id: "default"
  user_domain_id: "default"
  project_name: "service"
  username: "iotronic"
  password: "<secret>"
  
  # Service Registration
  service_type: "iot"
  service_name: "Stack4Things"
  service_description: "IoT Device Management Service"
  
  endpoints:
    public: "http://api.stack4things.local:8812"
    internal: "http://api.stack4things.local:8812"
    admin: "http://api.stack4things.local:8812"
  region: "RegionOne"
```

### 2. Neutron Integration

```yaml
# config/openstack/neutron.yaml
neutron:
  version: "2024.1"
  auth_url: "http://keystone:5000/v3"
  url: "http://neutron:9696"
  auth_type: "password"
  project_domain_name: "default"
  user_domain_name: "default"
  project_name: "service"
  username: "neutron"
  password: "<secret>"
  region_name: "RegionOne"
  
  # API Features
  api_version: "2.0"
  retries: 3
  timeout: 30
```

### 3. Designate Integration

```yaml
# config/openstack/designate.yaml
designate:
  version: "2024.1"
  auth_url: "http://keystone:5000/v3"
  url: "http://designate:9001"
  auth_type: "password"
  project_domain_name: "default"
  user_domain_name: "default"
  project_name: "service"
  username: "designate"
  password: "<secret>"
  region_name: "RegionOne"
  
  # DNS Features
  api_version: "2"
  retries: 3
```

## 📦 Python Client Libraries

### Versioni Supportate

```toml
# pyproject.toml - OpenStack Clients
[project.dependencies]
# OpenStack SDK (modern, recommended)
openstacksdk = "^2.0.0"  # Latest stable

# Legacy clients (for compatibility)
python-keystoneclient = "^5.0.0"
python-neutronclient = "^9.0.0"
python-designateclient = "^4.0.0"

# OpenStack Common Libraries
oslo-config = "^9.0.0"
oslo-log = "^5.0.0"
oslo-db = "^13.0.0"
oslo-messaging = "^13.0.0"
oslo-policy = "^4.0.0"
keystonemiddleware = "^12.0.0"
```

### OpenStack SDK (Modern Approach)

```python
# libraries/common/src/common/openstack.py
from openstack import connection

class OpenStackClient:
    def __init__(self, config):
        self.conn = connection.Connection(
            auth_url=config.auth_url,
            project_name=config.project_name,
            username=config.username,
            password=config.password,
            user_domain_id=config.user_domain_id,
            project_domain_id=config.project_domain_id,
            region_name=config.region_name,
        )
    
    def get_network_client(self):
        return self.conn.network
    
    def get_dns_client(self):
        return self.conn.dns
    
    def get_identity_client(self):
        return self.conn.identity
```

### Legacy Clients (Backward Compatibility)

```python
# For services that still use legacy clients
from keystoneauth1.identity import v3
from keystoneauth1 import session
from neutronclient.v2_0 import client as neutron_client
from designateclient.v2 import client as designate_client

class LegacyOpenStackClient:
    def __init__(self, config):
        auth = v3.Password(
            auth_url=config.auth_url,
            username=config.username,
            password=config.password,
            project_name=config.project_name,
            user_domain_id=config.user_domain_id,
            project_domain_id=config.project_domain_id,
        )
        sess = session.Session(auth=auth)
        
        self.neutron = neutron_client.Client(session=sess)
        self.designate = designate_client.Client(session=sess)
```

## 🗄️ Database Compatibility

### MySQL/MariaDB Configuration

```yaml
# config/database.yaml
database:
  type: "mysql"  # Compatibile con OpenStack
  driver: "pymysql"
  host: "mysql-host"  # Può essere stesso cluster OpenStack
  port: 3306
  database: "iotronic"
  username: "iotronic"
  password: "<secret>"
  
  # Connection Pool (compatibile oslo.db)
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
  pool_recycle: 3600
  pool_pre_ping: true
  
  # MySQL Specific
  charset: "utf8mb4"
  collation: "utf8mb4_unicode_ci"
```

### Shared Database Option

```yaml
# Option: Condividere cluster MySQL con OpenStack
database:
  shared_cluster: true
  cluster_host: "mysql-openstack-cluster"
  # Database separato per sicurezza
  database: "iotronic"
  # Stesse credenziali infrastruttura se necessario
```

## 🔐 Service Registration

### Registrazione in Keystone

```python
# scripts/register-openstack-service.py
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client as keystone_client

def register_stack4things_service():
    auth = v3.Password(
        auth_url="http://keystone:5000/v3",
        username="admin",
        password="admin",
        project_name="admin",
        user_domain_id="default",
        project_domain_id="default",
    )
    sess = session.Session(auth=auth)
    keystone = keystone_client.Client(session=sess)
    
    # Create service
    service = keystone.services.create(
        name="Stack4Things",
        type="iot",
        description="IoT Device Management Service"
    )
    
    # Create endpoints
    for endpoint_type in ['public', 'internal', 'admin']:
        keystone.endpoints.create(
            service=service.id,
            interface=endpoint_type,
            url=f"http://api.stack4things.local:8812",
            region="RegionOne"
        )
```

## 🧪 Testing Compatibility

### Test Matrix

```yaml
# tests/openstack/compatibility-matrix.yaml
test_matrix:
  openstack_versions:
    - "2024.1"  # Antelope
    - "2023.2"  # Zed
    - "2023.1"  # Yoga
  
  components:
    - keystone
    - neutron
    - designate
  
  test_scenarios:
    - service_registration
    - authentication
    - network_operations
    - dns_operations
    - error_handling
```

### Compatibility Tests

```python
# tests/openstack/test_keystone_compatibility.py
import pytest
from openstack import connection

@pytest.mark.parametrize("os_version", ["2024.1", "2023.2", "2023.1"])
def test_keystone_authentication(os_version):
    """Test authentication con diverse versioni Keystone"""
    conn = connection.Connection(
        auth_url=f"http://keystone-{os_version}:5000/v3",
        # ... config
    )
    assert conn.authenticate()
    
@pytest.mark.parametrize("os_version", ["2024.1", "2023.2", "2023.1"])
def test_neutron_api_compatibility(os_version):
    """Test Neutron API compatibility"""
    # Test network operations
    pass
```

## 📋 Checklist Compatibilità

### Pre-Deployment
- [ ] Verificare versione OpenStack installata
- [ ] Verificare versioni client libraries
- [ ] Test connessione Keystone
- [ ] Test connessione Neutron
- [ ] Test connessione Designate
- [ ] Verificare database compatibility

### Post-Deployment
- [ ] Registrare servizio in Keystone
- [ ] Creare endpoints
- [ ] Test autenticazione end-to-end
- [ ] Test operazioni network
- [ ] Test operazioni DNS
- [ ] Verificare logs per errori compatibilità

## 🔄 Upgrade Path

### Da Stack4Things v1.0
1. Database migration mantenendo MySQL
2. API compatibility layer se necessario
3. Gradual cutover

### OpenStack Upgrade
1. Test compatibility con nuova versione OpenStack
2. Update client libraries se necessario
3. Test integration completa
4. Deploy insieme a upgrade OpenStack

## 📚 References

- [OpenStack Releases](https://releases.openstack.org/)
- [OpenStack API Documentation](https://docs.openstack.org/api/)
- [OpenStack Python SDK](https://docs.openstack.org/openstacksdk/)
- [OpenStack Database Guide](https://docs.openstack.org/install-guide/database.html)


