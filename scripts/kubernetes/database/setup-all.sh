#!/bin/bash
# Complete database setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "🗄️  Setting up complete database infrastructure for Stack4Things v2.0"

# Step 1: MySQL/MariaDB HA
echo ""
echo "=== Step 1: Installing MySQL/MariaDB HA ==="
"$SCRIPT_DIR/setup-mysql.sh"

# Step 2: ProxySQL
echo ""
echo "=== Step 2: Installing ProxySQL ==="
"$SCRIPT_DIR/setup-proxysql.sh"

# Step 3: Backup automation
echo ""
echo "=== Step 3: Setting up backup automation ==="
"$SCRIPT_DIR/setup-backup.sh"

# Step 4: Test compatibility
echo ""
echo "=== Step 4: Testing OpenStack compatibility ==="
"$SCRIPT_DIR/test-openstack-compatibility.sh"

# Summary
echo ""
echo "🎉 Database infrastructure setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ MySQL/MariaDB HA installed"
echo "  ✅ ProxySQL installed"
echo "  ✅ Backup automation configured"
echo "  ✅ OpenStack compatibility verified"
echo ""
echo "📝 Connection Info:"
echo "  Direct MySQL: mariadb.stack4things-infrastructure.svc.cluster.local:3306"
echo "  Via ProxySQL: proxysql.stack4things-infrastructure.svc.cluster.local:3306"
echo ""
echo "📝 Next steps:"
echo "  1. Run database migrations:"
echo "     cd services/device-service && poetry run alembic upgrade head"
echo ""
echo "  2. Update service configuration:"
echo "     DATABASE_URL=mysql+pymysql://stack4things:stack4things@proxysql.stack4things-infrastructure.svc.cluster.local:3306/stack4things"

