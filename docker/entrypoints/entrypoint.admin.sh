#!/bin/bash
set -e

echo "========================================="
echo "DWC Admin Panel - Starting up..."
echo "========================================="

# =================================
# Environment Variable Checker
# =================================
echo "Checking required environment variables..."

MISSING_VARS=()

# Required variables
[ -z "$SECRET_KEY" ] && MISSING_VARS+=("SECRET_KEY")
[ -z "$NAS_API_TOKEN" ] && MISSING_VARS+=("NAS_API_TOKEN")

# Database variables (if using MariaDB)
if [ "$DATABASE_ENGINE" = "mariadb" ]; then
    [ -z "$DATABASE_NAME" ] && MISSING_VARS+=("DATABASE_NAME")
    [ -z "$DATABASE_USER" ] && MISSING_VARS+=("DATABASE_USER")
    [ -z "$DATABASE_PASSWORD" ] && MISSING_VARS+=("DATABASE_PASSWORD")
    [ -z "$DATABASE_HOST" ] && MISSING_VARS+=("DATABASE_HOST")
fi

# Check if any variables are missing
if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo ""
    echo "ERROR: Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please set these variables in your .env file or docker-compose.yml"
    echo "See .env.example for reference."
    exit 1
fi

echo "All required environment variables are set."

# =================================
# Optional: Show configuration
# =================================
if [ "$DEBUG" = "True" ]; then
    echo ""
    echo "Configuration:"
    echo "  DATABASE_ENGINE: ${DATABASE_ENGINE:-sqlite}"
    echo "  DATABASE_NAME: ${DATABASE_NAME:-dwc_server.db}"
    echo "  DEBUG: ${DEBUG:-False}"
    echo ""
fi

# Wait for database to be ready (if using MariaDB)
if [ "$DATABASE_ENGINE" = "mariadb" ]; then
    echo "Waiting for MariaDB to be ready..."

    max_retries=30
    retry_count=0

    while ! python -c "
import MySQLdb
MySQLdb.connect(
    host='${DATABASE_HOST:-mariadb}',
    user='${DATABASE_USER:-dwc}',
    passwd='${DATABASE_PASSWORD:-changeme}',
    db='${DATABASE_NAME:-dwc_server}',
    port=int('${DATABASE_PORT:-3306}')
)
" 2>/dev/null; do
        retry_count=$((retry_count + 1))
        if [ $retry_count -ge $max_retries ]; then
            echo "ERROR: Could not connect to MariaDB after $max_retries attempts"
            exit 1
        fi
        echo "MariaDB not ready yet... (attempt $retry_count/$max_retries)"
        sleep 2
    done

    echo "MariaDB is ready!"
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if credentials are provided
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput 2>/dev/null || echo "Superuser already exists or could not be created"
fi

# Create API service token if NAS_API_TOKEN is set
if [ -n "$NAS_API_TOKEN" ]; then
    echo "Creating API service token..."
    python manage.py shell -c "
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

user, created = User.objects.get_or_create(username='api_service', defaults={'is_staff': True})
Token.objects.filter(user=user).delete()
Token.objects.create(user=user, key='${NAS_API_TOKEN}')
print('API token configured for api_service user')
" 2>/dev/null || echo "API token already exists or could not be created"
fi

echo "========================================="
echo "Starting Gunicorn server on port ${DJANGO_PORT:-7999}..."
echo "========================================="

# Start gunicorn
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:${DJANGO_PORT:-7999} \
    --workers ${GUNICORN_WORKERS:-2} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -
