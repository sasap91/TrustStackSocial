#!/bin/bash
# TrustStackSocial Application Deployment Script
# Deploys the application code and installs dependencies

set -e

APP_DIR="/opt/truststacksocial"
REPO_URL="${REPO_URL:-https://github.com/yourusername/TrustStackSocial.git}"
BRANCH="${BRANCH:-main}"

echo "=================================="
echo "TrustStackSocial Application Deployment"
echo "=================================="
echo ""

# Check if running as truststack user
if [ "$USER" != "truststack" ]; then
    echo "Error: This script must be run as the 'truststack' user"
    echo "Run: sudo su - truststack"
    exit 1
fi

# Navigate to application directory
cd ${APP_DIR}

# Clone or update repository
echo "[1/5] Setting up application code..."
if [ -d ".git" ]; then
    echo "  Repository already exists, pulling latest changes..."
    git fetch origin
    git checkout ${BRANCH}
    git pull origin ${BRANCH}
else
    echo "  Cloning repository..."
    if [ -n "${REPO_URL}" ] && [ "${REPO_URL}" != "https://github.com/yourusername/TrustStackSocial.git" ]; then
        git clone -b ${BRANCH} ${REPO_URL} .
    else
        echo "  Error: REPO_URL not set. Please set it before running this script."
        echo "  Example: export REPO_URL=https://github.com/yourusername/TrustStackSocial.git"
        exit 1
    fi
fi

# Create virtual environment
echo ""
echo "[2/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo ""
echo "[3/5] Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "[4/5] Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "  ✓ Dependencies installed"

# Set up output directories
echo ""
echo "[5/5] Setting up directories..."
mkdir -p output
mkdir -p logs
chmod 755 output logs
echo "  ✓ Directories created"

# Create .env file placeholder (will be populated by load-secrets.sh)
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file template..."
    cat > .env << 'EOF'
# This file will be populated by load-secrets.sh
# Do not edit manually - secrets are managed via Google Secret Manager
OPENROUTER_API_KEY=
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
NOTION_API_KEY=
NOTION_PAGE_ID=
MASTODON_ACCESS_TOKEN=
MASTODON_API_BASE_URL=
EOF
    echo "  ✓ .env template created"
fi

# Initialize database
echo ""
echo "[6/6] Initializing database..."
source venv/bin/activate
python3 -c "from src.database import init_db; init_db(); print('Database initialized')" || {
    echo "  ⚠️  Database initialization failed, but continuing..."
}

# Migrate existing JSON files if they exist
if [ -d "output" ] && [ "$(ls -A output/*.json 2>/dev/null)" ]; then
    echo ""
    echo "Migrating existing JSON files to database..."
    python3 -c "from src.migrate_json_to_db import migrate_all; migrate_all('output')" || {
        echo "  ⚠️  Migration failed, but continuing..."
    }
fi

echo ""
echo "=================================="
echo "✓ Application deployment complete!"
echo "=================================="
echo ""
echo "Application location: ${APP_DIR}"
echo "Virtual environment: ${APP_DIR}/venv"
echo ""
echo "Next steps:"
echo "1. Run: ./deploy/load-secrets.sh to load API credentials"
echo "2. Run: ./deploy/setup-cron.sh to configure scheduled tasks"
echo "3. Run: sudo ./deploy/setup-api.sh to set up API service"
echo "4. Test the application: source venv/bin/activate && python main.py --help"
echo "5. Test the API: source venv/bin/activate && python api_server.py"
echo ""


