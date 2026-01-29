#!/bin/bash
# TrustStackSocial Secret Manager Integration
# Fetches secrets from Google Cloud Secret Manager and creates .env file

set -e

PROJECT_ID="truststacksocialsp"
APP_DIR="/opt/truststacksocial"
ENV_FILE="${APP_DIR}/.env"

# Secret names in Secret Manager
SECRET_OPENROUTER_API_KEY="openrouter-api-key"
SECRET_NOTION_API_KEY="notion-api-key"
SECRET_NOTION_PAGE_ID="notion-page-id"
SECRET_MASTODON_ACCESS_TOKEN="mastodon-access-token"
SECRET_MASTODON_API_BASE_URL="mastodon-api-base-url"
SECRET_REPLICATE_API_TOKEN="replicate-api-token"

echo "=================================="
echo "Loading Secrets from Secret Manager"
echo "=================================="
echo ""

# Check if gcloud is available
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI not found. Please install Google Cloud SDK first."
    exit 1
fi

# Set the project
gcloud config set project ${PROJECT_ID} --quiet

# Function to get secret value
get_secret() {
    local secret_name=$1
    local default_value=$2
    
    if gcloud secrets versions access latest --secret="${secret_name}" --project=${PROJECT_ID} 2>/dev/null; then
        gcloud secrets versions access latest --secret="${secret_name}" --project=${PROJECT_ID}
    else
        if [ -n "${default_value}" ]; then
            echo "${default_value}"
        else
            echo ""
        fi
    fi
}

# Fetch secrets
echo "[1/6] Fetching OpenRouter API key..."
OPENROUTER_API_KEY=$(get_secret ${SECRET_OPENROUTER_API_KEY})
if [ -z "${OPENROUTER_API_KEY}" ]; then
    echo "  ⚠️  Warning: OpenRouter API key not found in Secret Manager"
else
    echo "  ✓ OpenRouter API key retrieved"
fi

echo ""
echo "[2/6] Fetching Notion API key..."
NOTION_API_KEY=$(get_secret ${SECRET_NOTION_API_KEY})
if [ -z "${NOTION_API_KEY}" ]; then
    echo "  ⚠️  Warning: Notion API key not found in Secret Manager"
else
    echo "  ✓ Notion API key retrieved"
fi

echo ""
echo "[3/6] Fetching Notion Page ID..."
NOTION_PAGE_ID=$(get_secret ${SECRET_NOTION_PAGE_ID})
if [ -z "${NOTION_PAGE_ID}" ]; then
    echo "  ⚠️  Warning: Notion Page ID not found in Secret Manager"
else
    echo "  ✓ Notion Page ID retrieved"
fi

echo ""
echo "[4/6] Fetching Mastodon access token..."
MASTODON_ACCESS_TOKEN=$(get_secret ${SECRET_MASTODON_ACCESS_TOKEN})
if [ -z "${MASTODON_ACCESS_TOKEN}" ]; then
    echo "  ⚠️  Warning: Mastodon access token not found in Secret Manager"
else
    echo "  ✓ Mastodon access token retrieved"
fi

echo ""
echo "[5/6] Fetching Mastodon API base URL..."
MASTODON_API_BASE_URL=$(get_secret ${SECRET_MASTODON_API_BASE_URL} "https://mastodon.social")
if [ -z "${MASTODON_API_BASE_URL}" ]; then
    MASTODON_API_BASE_URL="https://mastodon.social"
    echo "  ⚠️  Using default Mastodon API base URL: ${MASTODON_API_BASE_URL}"
else
    echo "  ✓ Mastodon API base URL retrieved"
fi

echo ""
echo "[6/7] Fetching Replicate API token..."
REPLICATE_API_TOKEN=$(get_secret ${SECRET_REPLICATE_API_TOKEN})
if [ -z "${REPLICATE_API_TOKEN}" ]; then
    echo "  ⚠️  Warning: Replicate API token not found in Secret Manager (image generation will be disabled)"
else
    echo "  ✓ Replicate API token retrieved"
fi

# Create .env file
echo ""
echo "[7/7] Creating .env file..."
cat > ${ENV_FILE} << EOF
# Openrouter API Configuration
OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Notion API Configuration
NOTION_API_KEY=${NOTION_API_KEY}
NOTION_PAGE_ID=${NOTION_PAGE_ID}

# Mastodon API Configuration
MASTODON_ACCESS_TOKEN=${MASTODON_ACCESS_TOKEN}
MASTODON_API_BASE_URL=${MASTODON_API_BASE_URL}

# Replicate API Configuration (optional - for image generation)
REPLICATE_API_TOKEN=${REPLICATE_API_TOKEN}
EOF

# Set proper permissions
chmod 600 ${ENV_FILE}
chown truststack:truststack ${ENV_FILE}

echo "  ✓ .env file created at ${ENV_FILE}"
echo "  ✓ File permissions set (read-only for owner)"

echo ""
echo "=================================="
echo "✓ Secrets loaded successfully!"
echo "=================================="
echo ""
echo "To create/update secrets in Secret Manager, run:"
echo "  gcloud secrets create openrouter-api-key --data-file=- <<< 'your-key'"
echo "  gcloud secrets create notion-api-key --data-file=- <<< 'your-key'"
echo "  gcloud secrets create notion-page-id --data-file=- <<< 'your-page-id'"
echo "  gcloud secrets create mastodon-access-token --data-file=- <<< 'your-token'"
echo "  gcloud secrets create mastodon-api-base-url --data-file=- <<< 'https://mastodon.social'"
echo "  gcloud secrets create replicate-api-token --data-file=- <<< 'your-token'"
echo ""
echo "Or update existing secrets:"
echo "  echo -n 'your-key' | gcloud secrets versions add openrouter-api-key --data-file=-"
echo ""


