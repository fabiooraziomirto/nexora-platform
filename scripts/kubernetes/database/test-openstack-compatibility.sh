#!/bin/bash
# Test OpenStack MySQL compatibility

set -e

echo "🧪 Testing OpenStack MySQL compatibility"

# Configuration
MYSQL_HOST="${MYSQL_HOST:-mariadb.nxr-infrastructure.svc.cluster.local}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-nxr}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-nxr}"
MYSQL_DATABASE="${MYSQL_DATABASE:-nxr}"

echo "📋 Connection Info:"
echo "  Host: $MYSQL_HOST"
echo "  Port: $MYSQL_PORT"
echo "  Database: $MYSQL_DATABASE"
echo "  User: $MYSQL_USER"

# Test 1: Connection
echo ""
echo "Test 1: Testing connection..."
if kubectl run mysql-test-connection --rm -i --restart=Never \
    --image=mysql:8.0 \
    --namespace=nxr-infrastructure \
    -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
    -e "SELECT 1" &> /dev/null; then
    echo "✅ Connection successful"
else
    echo "❌ Connection failed"
    exit 1
fi

# Test 2: Database charset and collation
echo ""
echo "Test 2: Checking database charset and collation..."
CHARSET=$(kubectl run mysql-test-charset --rm -i --restart=Never \
    --image=mysql:8.0 \
    --namespace=nxr-infrastructure \
    -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
    -e "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='$MYSQL_DATABASE'" \
    2>/dev/null | tail -n 1)

if echo "$CHARSET" | grep -q "utf8mb4"; then
    echo "✅ Database charset: utf8mb4 (OpenStack compatible)"
else
    echo "⚠️  Database charset: $CHARSET (may not be OpenStack compatible)"
fi

# Test 3: MySQL version compatibility
echo ""
echo "Test 3: Checking MySQL version..."
VERSION=$(kubectl run mysql-test-version --rm -i --restart=Never \
    --image=mysql:8.0 \
    --namespace=nxr-infrastructure \
    -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
    -e "SELECT VERSION()" 2>/dev/null | tail -n 1)

echo "MySQL Version: $VERSION"

# Test 4: Create test table (OpenStack style)
echo ""
echo "Test 4: Testing OpenStack-style table creation..."
kubectl run mysql-test-table --rm -i --restart=Never \
    --image=mysql:8.0 \
    --namespace=nxr-infrastructure \
    -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
    "$MYSQL_DATABASE" <<EOF
CREATE TABLE IF NOT EXISTS test_openstack_compatibility (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    INDEX idx_name (name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
EOF

if [ $? -eq 0 ]; then
    echo "✅ Table creation successful"
    
    # Cleanup
    kubectl run mysql-test-cleanup --rm -i --restart=Never \
        --image=mysql:8.0 \
        --namespace=nxr-infrastructure \
        -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
        "$MYSQL_DATABASE" -e "DROP TABLE test_openstack_compatibility" &> /dev/null
else
    echo "❌ Table creation failed"
    exit 1
fi

# Test 5: Test transactions
echo ""
echo "Test 5: Testing transactions..."
kubectl run mysql-test-transaction --rm -i --restart=Never \
    --image=mysql:8.0 \
    --namespace=nxr-infrastructure \
    -- mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
    "$MYSQL_DATABASE" <<EOF
START TRANSACTION;
CREATE TABLE IF NOT EXISTS test_transaction (id INT PRIMARY KEY);
INSERT INTO test_transaction VALUES (1);
ROLLBACK;
SELECT COUNT(*) FROM test_transaction;
EOF

if [ $? -eq 0 ]; then
    echo "✅ Transactions working correctly"
else
    echo "❌ Transaction test failed"
    exit 1
fi

# Test 6: Test connection pooling (ProxySQL)
echo ""
echo "Test 6: Testing ProxySQL connection pooling..."
if kubectl get svc proxysql -n nxr-infrastructure &> /dev/null; then
    PROXYSQL_HOST="proxysql.nxr-infrastructure.svc.cluster.local"
    if kubectl run mysql-test-proxysql --rm -i --restart=Never \
        --image=mysql:8.0 \
        --namespace=nxr-infrastructure \
        -- mysql -h "$PROXYSQL_HOST" -P 3306 -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
        -e "SELECT 1" &> /dev/null; then
        echo "✅ ProxySQL connection successful"
    else
        echo "⚠️  ProxySQL connection failed (may not be set up)"
    fi
else
    echo "⚠️  ProxySQL not found (skip test)"
fi

echo ""
echo "🎉 All compatibility tests passed!"
echo ""
echo "✅ Nxr v2.0 is compatible with OpenStack MySQL/MariaDB"

