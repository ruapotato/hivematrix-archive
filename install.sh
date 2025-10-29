#!/bin/bash
#
# HiveMatrix Archive - Minimal Installation Script
# This script only sets up Python dependencies.
# Manual configuration is required - see README.md
#

set -e  # Exit on error

APP_NAME="archive"
APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$APP_DIR")"
HELM_DIR="$PARENT_DIR/hivematrix-helm"

echo "=========================================="
echo "  Installing HiveMatrix Archive"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check Python version
echo -e "${YELLOW}Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓ Found Python $PYTHON_VERSION${NC}"
echo ""

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ -d "pyenv" ]; then
    echo "  Virtual environment already exists"
else
    python3 -m venv pyenv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi
echo ""

# Activate virtual environment
source pyenv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"
echo ""

# Install dependencies
if [ -f "requirements.txt" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
    echo ""
fi

# Create instance directory if needed
if [ ! -d "instance" ]; then
    echo -e "${YELLOW}Creating instance directory...${NC}"
    mkdir -p instance
    echo -e "${GREEN}✓ Instance directory created${NC}"
    echo ""
fi

# Create minimal .flaskenv so init_db.py can run
# Helm will regenerate this with full config later
if [ ! -f ".flaskenv" ]; then
    echo -e "${YELLOW}Creating minimal .flaskenv...${NC}"
    cat > .flaskenv <<EOF
FLASK_APP=app
FLASK_ENV=development
SERVICE_NAME=archive
SERVICE_PORT=5012
CORE_SERVICE_URL=http://localhost:5000
HELM_SERVICE_URL=http://localhost:5004
CODEX_SERVICE_URL=http://localhost:5010
LEDGER_SERVICE_URL=http://localhost:5011
EOF
    echo -e "${GREEN}✓ Minimal .flaskenv created${NC}"
    echo -e "${YELLOW}  (Helm will regenerate with full config after setup)${NC}"
    echo ""
fi

# Symlink services.json from Helm (if Helm is installed)
echo -e "${YELLOW}Linking services configuration...${NC}"
if [ -d "$HELM_DIR" ] && [ -f "$HELM_DIR/services.json" ]; then
    ln -sf ../hivematrix-helm/services.json services.json
    echo -e "${GREEN}✓ Linked to Helm services.json${NC}"
else
    echo -e "${YELLOW}⚠ Helm not found. Service-to-service calls will be limited.${NC}"
    echo -e "${YELLOW}  Install Helm first, then re-run: ./install.sh${NC}"
fi
echo ""

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x scheduled_snapshots.py 2>/dev/null || true
chmod +x test_workflow.py 2>/dev/null || true
echo -e "${GREEN}✓ Scripts are executable${NC}"
echo ""

# Run database initialization
echo -e "${YELLOW}Initializing database...${NC}"
if [ -f "init_db.py" ]; then
    python init_db.py
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Database initialized${NC}"
    else
        echo -e "${YELLOW}⚠ Database initialization encountered an issue${NC}"
        echo -e "${YELLOW}  You may need to configure database settings manually${NC}"
    fi
else
    echo -e "${YELLOW}⚠ init_db.py not found, skipping database setup${NC}"
fi
echo ""

echo "=========================================="
echo -e "${GREEN}  Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Archive service is ready to use!"
echo ""
echo "The service will be started automatically by Helm."
echo "You can also start it manually with:"
echo "  python run.py"
echo ""
echo "Health check:"
echo "  curl http://localhost:5012/health"
echo ""
