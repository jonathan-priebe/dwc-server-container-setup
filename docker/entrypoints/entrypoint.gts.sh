#!/bin/bash
set -e

echo "========================================="
echo "DWC GTS Server - Starting up..."
echo "========================================="

# Wait for MariaDB to be ready (using root to create database/user if needed)
echo "Waiting for MariaDB at ${MARIADB_HOST}..."

max_retries=30
retry_count=0

while ! mysqladmin ping -h "${MARIADB_HOST}" -u root -p"${MARIADB_ROOT_PASSWORD}" --silent 2>/dev/null; do
    retry_count=$((retry_count + 1))
    if [ $retry_count -ge $max_retries ]; then
        echo "ERROR: Could not connect to MariaDB after $max_retries attempts"
        exit 1
    fi
    echo "MariaDB is unavailable - sleeping (attempt $retry_count/$max_retries)"
    sleep 2
done

echo "MariaDB is up!"

# Create GTS database and user if they don't exist
echo "Ensuring GTS database and user exist..."
mysql -h "${MARIADB_HOST}" -u root -p"${MARIADB_ROOT_PASSWORD}" -e "
CREATE DATABASE IF NOT EXISTS ${GTS_DB_NAME} CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER IF NOT EXISTS '${GTS_DB_USER}'@'%' IDENTIFIED BY '${GTS_DB_PASSWORD}';
GRANT ALL PRIVILEGES ON ${GTS_DB_NAME}.* TO '${GTS_DB_USER}'@'%';
FLUSH PRIVILEGES;
" 2>/dev/null || echo "Database/user setup completed (may already exist)"

# Check if GTS database has data
TABLE_COUNT=$(mysql -h "${MARIADB_HOST}" -u "${GTS_DB_USER}" -p"${GTS_DB_PASSWORD}" "${GTS_DB_NAME}" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${GTS_DB_NAME}';" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -eq "0" ] || [ "$TABLE_COUNT" = "0" ]; then
    echo "Initializing GTS database..."

    # Import GTS schema
    mysql -h "${MARIADB_HOST}" -u "${GTS_DB_USER}" -p"${GTS_DB_PASSWORD}" "${GTS_DB_NAME}" < /gts_dump.sql

    if [ $? -eq 0 ]; then
        echo "GTS database initialized successfully!"
    else
        echo "ERROR: Failed to import GTS schema"
        exit 1
    fi
else
    echo "GTS database already has $TABLE_COUNT tables, skipping initialization."
fi

# Update connection strings in Web.config if needed
CONFIG_FILE="/var/www/gts/Web.config"
if [ -f "$CONFIG_FILE" ]; then
    echo "Updating connection strings in Web.config..."
    sed -i "s/Server=[^;]*;/Server=${MARIADB_HOST};/g" "$CONFIG_FILE"
    sed -i "s/User Id=[^;]*;/User Id=${GTS_DB_USER};/g" "$CONFIG_FILE"
    sed -i "s/Password=[^;]*;/Password=${GTS_DB_PASSWORD};/g" "$CONFIG_FILE"
    sed -i "s/Database=[^;]*;/Database=${GTS_DB_NAME};/g" "$CONFIG_FILE"
    # Fix charset for MariaDB 11 compatibility (utf8mb3 -> utf8)
    sed -i "s/charset=utf8mb3/charset=utf8/g" "$CONFIG_FILE"
    sed -i "s/charset=utf8;/charset=utf8;SslMode=None;/g" "$CONFIG_FILE"
fi

echo "========================================="
echo "Starting Apache with mod_mono on port 9002..."
echo "========================================="

# Start Apache in foreground
exec apachectl -D FOREGROUND
