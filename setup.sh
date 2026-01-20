#!/bin/bash
# TrustStack Social Media Automation - Setup Script

echo "=================================="
echo "TrustStack Social Setup"
echo "=================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cat > .env << 'EOF'
# Openrouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Notion API Configuration
NOTION_API_KEY=your_notion_api_key_here
NOTION_PAGE_ID=your_notion_page_id_here

# Mastodon API Configuration
MASTODON_ACCESS_TOKEN=your_mastodon_access_token_here
MASTODON_API_BASE_URL=https://mastodon.social
EOF
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and add your API credentials!"
else
    echo ""
    echo "✓ .env file already exists"
fi

# Create output directory
mkdir -p output

echo ""
echo "=================================="
echo "✓ Setup complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API credentials"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the application: python main.py --help"
echo ""
echo "Quick start:"
echo "  python main.py full-workflow"
echo ""

