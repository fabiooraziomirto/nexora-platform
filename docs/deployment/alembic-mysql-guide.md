# Alembic Configuration for MySQL/MariaDB

## Overview

Alembic is configured for MySQL/MariaDB with OpenStack compatibility.

## Configuration

See `services/device-service/alembic.ini` for configuration.

## MySQL-Specific Considerations

### 1. Charset and Collation

Always use `utf8mb4` charset and `utf8mb4_unicode_ci` collation:

```python
from sqlalchemy import create_engine

engine = create_engine(
    "mysql+pymysql://user:pass@host/db?charset=utf8mb4",
    connect_args={
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"
    }
)
```

### 2. Table Creation

```python
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.mysql import CHAR

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(CHAR(36), primary_key=True)  # UUID as CHAR(36)
    name = Column(String(255), nullable=False)
    
    __table_args__ = (
        Index('idx_name', 'name'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4'}
    )
```

## Usage

### Create Migration

```bash
cd services/device-service
poetry run alembic revision --autogenerate -m "add new column"
```

### Apply Migrations

```bash
# Upgrade to latest
poetry run alembic upgrade head

# Upgrade one version
poetry run alembic upgrade +1

# Downgrade one version
poetry run alembic downgrade -1

# Downgrade to specific revision
poetry run alembic downgrade <revision>
```

### Check Current Revision

```bash
poetry run alembic current
```

### Show Migration History

```bash
poetry run alembic history
```

## OpenStack Compatibility

### Shared Database Setup

When using shared OpenStack MySQL:

1. **Create database** (if not exists):
   ```sql
   CREATE DATABASE stack4things CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

2. **Update alembic.ini**:
   ```ini
   sqlalchemy.url = mysql+pymysql://stack4things:password@openstack-mysql:3306/stack4things
   ```

3. **Run migrations**:
   ```bash
   poetry run alembic upgrade head
   ```

## Troubleshooting

### Migration Fails

```bash
# Check current revision
poetry run alembic current

# Check migration history
poetry run alembic history

# Manually fix and continue
poetry run alembic stamp <revision>
```

### Connection Issues

```bash
# Test connection
mysql -h host -u user -p database

# Check SQLAlchemy connection
python -c "from sqlalchemy import create_engine; engine = create_engine('mysql+pymysql://...'); engine.connect()"
```

### Encoding Issues

Ensure `utf8mb4` is used:

```sql
SHOW CREATE DATABASE stack4things;
ALTER DATABASE stack4things CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

