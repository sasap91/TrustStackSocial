#!/bin/bash
# Script to generate social media post with news, logo, and comic image

set -e

echo "=================================="
echo "TrustStack Social Media Post Generator"
echo "=================================="
echo ""

# Activate virtual environment
cd "$(dirname "$0")"
source venv/bin/activate

# Check if dependencies are installed
echo "Checking dependencies..."
python3 -c "import sqlalchemy, yaml, replicate, telegram" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install -r requirements.txt
}

echo "✓ Dependencies ready"
echo ""

# Generate the post
echo "Generating post with news, logo, and comic image..."
echo ""

python3 main.py generate-pending-post --style professional --max-articles 3

echo ""
echo "=================================="
echo "✓ Done! Check your Telegram for approval"
echo "=================================="
