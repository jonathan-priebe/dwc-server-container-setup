#!/bin/bash
set -e

echo "========================================="
echo "DWC GameSpy Server - Starting up..."
echo "========================================="

# =================================
# Environment Variable Checker
# =================================
echo "Checking required environment variables..."

MISSING_VARS=()

# Required variables
[ -z "$DATABASE_URL" ] && [ -z "$API_BASE_URL" ] && MISSING_VARS+=("DATABASE_URL or API_BASE_URL")
[ -z "$NAS_API_TOKEN" ] && MISSING_VARS+=("NAS_API_TOKEN")

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
if [ "$LOG_LEVEL" = "DEBUG" ]; then
    echo ""
    echo "Configuration:"
    echo "  API_BASE_URL: ${API_BASE_URL:-not set}"
    echo "  LOG_LEVEL: ${LOG_LEVEL:-INFO}"
    echo ""
fi

echo "========================================="
echo "Starting GameSpy servers..."
echo "========================================="

# Start the GameSpy server
exec python -m dwc_server.main
