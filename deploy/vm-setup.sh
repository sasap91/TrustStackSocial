#!/bin/bash
# TrustStackSocial VM Initial Setup Script
# Run this script on the VM to configure the system environment

set -e

echo "=================================="
echo "TrustStackSocial VM Setup"
echo "=================================="
echo ""

# Update system packages
echo "[1/6] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Install Python 3.10+ and pip
echo ""
echo "[2/6] Installing Python 3.10+ and pip..."
sudo apt-get install -y -qq python3 python3-pip python3-venv python3-dev

# Verify Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "  ✓ Python ${PYTHON_VERSION} installed"

# Install git
echo ""
echo "[3/6] Installing git..."
sudo apt-get install -y -qq git

# Install Google Cloud SDK (for Secret Manager access)
echo ""
echo "[4/6] Installing Google Cloud SDK..."
if ! command -v gcloud &> /dev/null; then
    echo "  Installing gcloud CLI..."
    curl https://sdk.cloud.google.com | bash -s -- --disable-prompts
    export PATH="$HOME/google-cloud-sdk/bin:$PATH"
    gcloud components install gke-gcloud-auth-plugin --quiet
else
    echo "  ✓ gcloud CLI already installed"
fi

# Install Secret Manager client library dependencies
echo ""
echo "  Installing Secret Manager dependencies..."
sudo apt-get install -y -qq build-essential libffi-dev libssl-dev

# Create application user
echo ""
echo "[5/6] Creating application user..."
if ! id "truststack" &>/dev/null; then
    sudo useradd -m -s /bin/bash truststack
    echo "  ✓ Created user 'truststack'"
else
    echo "  ✓ User 'truststack' already exists"
fi

# Set up application directory structure
echo ""
echo "[6/6] Setting up application directories..."
sudo mkdir -p /opt/truststacksocial
sudo mkdir -p /opt/truststacksocial/output
sudo mkdir -p /opt/truststacksocial/logs
sudo chown -R truststack:truststack /opt/truststacksocial

# Configure automatic security updates
echo ""
echo "Configuring automatic security updates..."
sudo apt-get install -y -qq unattended-upgrades
sudo dpkg-reconfigure -f noninteractive unattended-upgrades || true

# Configure firewall (if ufw is available)
if command -v ufw &> /dev/null; then
    echo ""
    echo "Configuring firewall..."
    sudo ufw --force enable
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    echo "  ✓ Firewall configured (outbound allowed, inbound denied)"
fi

echo ""
echo "=================================="
echo "✓ VM setup complete!"
echo "=================================="
echo ""
echo "System configuration:"
echo "  Python: $(python3 --version)"
echo "  Git: $(git --version)"
echo "  Application user: truststack"
echo "  Application directory: /opt/truststacksocial"
echo ""
echo "Next steps:"
echo "1. Run: ./deploy/deploy-app.sh to deploy the application"
echo "2. Or manually:"
echo "   - Switch to truststack user: sudo su - truststack"
echo "   - Clone the repository to /opt/truststacksocial"
echo ""


