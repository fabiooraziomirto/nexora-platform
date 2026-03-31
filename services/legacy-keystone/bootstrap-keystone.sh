#!/usr/bin/env bash
set -euo pipefail

mkdir -p /etc/keystone /var/lib/keystone /etc/apache2/sites-enabled /etc/apache2/conf-enabled

if [ ! -f /etc/keystone/keystone.conf ]; then
  cp /config/keystone.conf /etc/keystone/keystone.conf
fi

if [ ! -f /etc/apache2/sites-enabled/keystone.conf ]; then
  cp /config/keystone-apache.conf /etc/apache2/sites-enabled/keystone.conf
fi

if [ ! -f /var/lib/keystone/.db_bootstrapped ]; then
  keystone-manage db_sync
  keystone-manage bootstrap \
    --bootstrap-password "${KEYSTONE_ADMIN_PASSWORD:-admin}" \
    --bootstrap-admin-url "http://legacy-keystone:5000/v3/" \
    --bootstrap-internal-url "http://legacy-keystone:5000/v3/" \
    --bootstrap-public-url "http://localhost:15000/v3/" \
    --bootstrap-region-id "RegionOne"
  touch /var/lib/keystone/.db_bootstrapped
fi

if [ ! -d /etc/keystone/fernet-keys ]; then
  keystone-manage fernet_setup --keystone-user keystone --keystone-group keystone
fi
if [ ! -d /etc/keystone/credential-keys ]; then
  keystone-manage credential_setup --keystone-user keystone --keystone-group keystone
fi

chown -R keystone:keystone /var/lib/keystone

exec apache2ctl -D FOREGROUND
