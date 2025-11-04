# Stack4Things v2.0 - OpenStack Compatibility Requirements

## 🎯 Compatibilità OpenStack

Stack4Things v2.0 è progettato per essere **completamente compatibile** con l'ultima versione di OpenStack.

## 📊 Versioni OpenStack Supportate

| Release | Codename | Release Date | Status | Support Level |
|---------|----------|--------------|--------|---------------|
| **2024.1** | Antelope | Apr 2024 | ✅ **Target** | Full Support |
| **2023.2** | Zed | Oct 2023 | ✅ Supported | Full Support |
| **2023.1** | Yoga | Apr 2023 | ✅ Supported | Full Support |
| **2022.2** | Wallaby | Oct 2022 | ⚠️ Limited | Maintenance Mode |
| **2022.1** | Victoria | Apr 2022 | ❌ EOL | Not Supported |

**Versione Target**: OpenStack 2024.1 (Antelope) o superiore

## 🔧 Componenti OpenStack Integrati

### Keystone (Identity Service)
- **Version**: Latest (2024.1+)
- **Integration**: 
  - Service registration
  - Token validation
  - User/project management
  - Role-based access control
- **Client Libraries**:
  - `openstacksdk>=2.0.0` (modern)
  - `python-keystoneclient>=5.0.0` (legacy compatibility)

### Neutron (Network Service)
- **Version**: Latest (2024.1+)
- **Integration**:
  - Port management
  - Network creation
  - Subnet management
  - Security groups
- **Client Libraries**:
  - `openstacksdk>=2.0.0`
  - `python-neutronclient>=9.0.0`

### Designate (DNS Service)
- **Version**: Latest (2024.1+)
- **Integration**:
  - DNS record management
  - Zone management
  - Record validation
- **Client Libraries**:
  - `openstacksdk>=2.0.0`
  - `python-designateclient>=4.0.0`

## 🗄️ Database Compatibility

### MySQL/MariaDB
- **Version**: MariaDB 10.11+ / MySQL 8.0+
- **Compatibility**: Standard OpenStack database
- **Features**:
  - UTF8MB4 charset
  - JSON support (MySQL 8.0+)
  - Replication support
  - Clustering support
- **Shared Infrastructure**: Possibilità di condividere cluster MySQL con OpenStack

### Connection String
```
mysql+pymysql://iotronic:password@mysql-host:3306/iotronic?charset=utf8mb4
```

## 📦 OpenStack Client Libraries

### Requirements

```toml
# pyproject.toml
[project.dependencies]
# Modern OpenStack SDK (recommended)
openstacksdk = "^2.0.0"

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

## 🔐 Service Registration

Stack4Things deve essere registrato come servizio OpenStack in Keystone:

```bash
# Service type
openstack service create iot --name Stack4Things

# Endpoints
openstack endpoint create --region RegionOne iot public http://api.stack4things.local:8812
openstack endpoint create --region RegionOne iot internal http://api.stack4things.local:8812
openstack endpoint create --region RegionOne iot admin http://api.stack4things.local:8812
```

## ✅ Compatibility Checklist

### Pre-Deployment
- [ ] Verificare versione OpenStack installata
- [ ] Verificare versioni client libraries compatibili
- [ ] Test connessione Keystone
- [ ] Test connessione Neutron
- [ ] Test connessione Designate
- [ ] Verificare database compatibility (MySQL/MariaDB)

### Post-Deployment
- [ ] Registrare servizio in Keystone
- [ ] Creare endpoints in Keystone
- [ ] Test autenticazione end-to-end
- [ ] Test operazioni network (Neutron)
- [ ] Test operazioni DNS (Designate)
- [ ] Verificare logs per errori compatibilità

## 📚 References

- [OpenStack Releases](https://releases.openstack.org/)
- [OpenStack API Documentation](https://docs.openstack.org/api/)
- [OpenStack Python SDK](https://docs.openstack.org/openstacksdk/)
- [OpenStack Database Guide](https://docs.openstack.org/install-guide/database.html)


