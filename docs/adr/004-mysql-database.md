# ADR-004: Database - MySQL/MariaDB (OpenStack Compatible)

## Status
**Accepted** - 2024-01-XX

## Context

Stack4Things v2.0 deve integrarsi perfettamente con OpenStack esistente e mantenere compatibilità con l'infrastruttura attuale. OpenStack utilizza MySQL/MariaDB come database standard per tutti i suoi servizi.

Requisiti:
- Compatibilità con database OpenStack esistente
- Condivisione infrastructure database se necessario
- Standard OpenStack per database
- Supporto per tutte le versioni OpenStack moderne

## Decision

Utilizzare **MySQL/MariaDB** come database principale invece di PostgreSQL.

**Versione Target**: MariaDB 10.11+ / MySQL 8.0+

## Motivazioni

### Compatibilità OpenStack
- ✅ **Standard OpenStack**: MySQL/MariaDB è il database standard OpenStack
- ✅ **Shared Infrastructure**: Possibilità di condividere database cluster con OpenStack
- ✅ **Migration Path**: Più semplice migrare dati se stesso database
- ✅ **Tooling**: Stessi tool di backup/monitoring di OpenStack

### Compatibilità Librerie
- ✅ **python-openstackclient**: Progettato per MySQL/MariaDB
- ✅ **oslo.db**: Ottimizzato per MySQL/MariaDB
- ✅ **SQLAlchemy**: Supporto maturo per MySQL/MariaDB

### Performance
- ✅ Performance eccellenti per workload OpenStack-like
- ✅ Replication nativa matura
- ✅ Clustering supportato

### Operations
- ✅ Team già competente (stesso di OpenStack)
- ✅ Monitoring tools già configurati
- ✅ Backup procedures già stabilite

## Consequences

### Positive
- ✅ Compatibilità totale con OpenStack
- ✅ Possibilità di shared database infrastructure
- ✅ Tooling comune
- ✅ Team expertise esistente

### Negative
- ⚠️ Alcune feature avanzate PostgreSQL non disponibili (JSON queries, array types)
- ⚠️ Meno "modern" rispetto a PostgreSQL

### Mitigation
- JSON support in MySQL 8.0+ è ottimo
- Features avanzate non necessarie per Stack4Things
- Compatibilità OpenStack più importante

## Alternatives Considered

### PostgreSQL
- ✅ Features avanzate
- ✅ JSON nativo migliore
- ❌ Non standard OpenStack
- ❌ Incompatibilità con infrastructure esistente
- ❌ Richiede database separato

### MongoDB/DocumentDB
- ✅ Document-oriented
- ❌ Non standard OpenStack
- ❌ Incompatibilità totale
- ❌ Troppo diverso

## Configuration

### Connection String
```
mysql+pymysql://iotronic:password@mysql-host:3306/iotronic
```

### SQLAlchemy Configuration
```python
# Supporto per MySQL/MariaDB
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import pymysql

engine = create_engine(
    "mysql+pymysql://user:pass@host/db",
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

### Alembic Configuration
```ini
# alembic.ini
[alembic]
sqlalchemy.url = mysql+pymysql://user:pass@host/db

[alembic:hook]
prepend_sys_path = .
```

## Migration Considerations

### Da Stack4Things v1.0
- Database schema compatibile
- Stesse tabelle MySQL
- Migration più semplice

### Shared Database
- Possibilità di condividere cluster MySQL OpenStack
- Separate database per sicurezza
- Shared connection pool possibile

## References

- [OpenStack Database Guide](https://docs.openstack.org/install-guide/database.html)
- [MySQL 8.0 Documentation](https://dev.mysql.com/doc/refman/8.0/en/)
- [MariaDB Documentation](https://mariadb.com/kb/en/documentation/)
- [SQLAlchemy MySQL Dialect](https://docs.sqlalchemy.org/en/14/dialects/mysql.html)


