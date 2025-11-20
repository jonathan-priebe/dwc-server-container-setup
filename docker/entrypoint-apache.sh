#!/bin/sh
set -e

echo "Starting DWC Network Server Emulator (Python 3)..."

# Start Python master server in background
cd /app
python3 dwc_server/main.py &
PYTHON_PID=$!

echo "Python servers started (PID: $PYTHON_PID)"
echo "Waiting 2 seconds for servers to initialize..."
sleep 2

# Start Apache in foreground
echo "Starting Apache..."
exec /usr/local/apache2/bin/httpd -D FOREGROUND
