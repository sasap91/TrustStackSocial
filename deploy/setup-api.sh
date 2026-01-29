#!/bin/bash
# TrustStackSocial API Setup Script
# Sets up FastAPI application as a systemd service

set -e

APP_DIR="/opt/truststacksocial"
SERVICE_NAME="truststacksocial-api"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
API_PORT="${API_PORT:-8000}"

echo "=================================="
echo "TrustStackSocial API Setup"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

# Check if application directory exists
if [ ! -d "${APP_DIR}" ]; then
    echo "Error: Application directory not found: ${APP_DIR}"
    echo "Please run deploy-app.sh first"
    exit 1
fi

# Create systemd service file
echo "[1/4] Creating systemd service..."
cat > ${SERVICE_FILE} << EOF
[Unit]
Description=TrustStackSocial FastAPI Application
After=network.target

[Service]
Type=simple
User=truststack
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin"
Environment="API_PORT=${API_PORT}"
Environment="API_HOST=0.0.0.0"
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "  ✓ Created service file: ${SERVICE_FILE}"

# Reload systemd
echo ""
echo "[2/4] Reloading systemd..."
systemctl daemon-reload

# Enable service
echo ""
echo "[3/4] Enabling service..."
systemctl enable ${SERVICE_NAME}

# Start service
echo ""
echo "[4/4] Starting service..."
systemctl start ${SERVICE_NAME}

# Wait a moment and check status
sleep 2
if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo "  ✓ Service started successfully"
else
    echo "  ⚠️  Service may have issues starting. Check status with: systemctl status ${SERVICE_NAME}"
fi

echo ""
echo "=================================="
echo "✓ API setup complete!"
echo "=================================="
echo ""
echo "Service management:"
echo "  Start:   sudo systemctl start ${SERVICE_NAME}"
echo "  Stop:    sudo systemctl stop ${SERVICE_NAME}"
echo "  Status:  sudo systemctl status ${SERVICE_NAME}"
echo "  Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "API will be available at:"
echo "  http://localhost:${API_PORT}"
echo "  http://localhost:${API_PORT}/docs (Swagger UI)"
echo ""
