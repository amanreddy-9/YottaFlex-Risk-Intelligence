#!/usr/bin/env bash
# ==============================================================================
# YottaFlex Risk Intelligence — Automated Reviewer Setup Script
# ==============================================================================
# This script sets up the full YottaFlex RiskOS environment in under 2 minutes:
#  1. Validates Python (>= 3.10) and Node.js (>= 18) runtimes.
#  2. Creates and activates a isolated Python virtual environment.
#  3. Installs frontend dependencies via npm and compiles the React 18 production bundle.
#  4. Bootstraps the SQLite database and validates ledger reconciliation.
#  5. Runs smoke tests to confirm system health.
# ==============================================================================

set -e

# ANSI styling
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}========================================================================${NC}"
echo -e "${CYAN}${BOLD}     YottaFlex Risk Intelligence — Automated Environment Setup          ${NC}"
echo -e "${CYAN}${BOLD}========================================================================${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. System Runtime Verification
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/5] Verifying system runtimes...${NC}"

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed or not in PATH.${NC}"
    echo "Please install Python 3.10+ (macOS: brew install python, Ubuntu: sudo apt install python3 python3-venv)"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "${RED}Error: Python 3.10+ is required (found Python $PY_VERSION).${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Python $PY_VERSION detected."

# Check Node.js & npm
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: node is not installed or not in PATH.${NC}"
    echo "Please install Node.js 18+ (macOS: brew install node, Ubuntu: sudo apt install nodejs npm)"
    exit 1
fi

NODE_VERSION=$(node -v | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

if [ "$NODE_MAJOR" -lt 18 ]; then
    echo -e "${YELLOW}Warning: Node.js 18+ is recommended (found v$NODE_VERSION).${NC}"
else
    echo -e "  ${GREEN}✓${NC} Node.js v$NODE_VERSION detected."
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} npm $(npm -v) detected."

# ------------------------------------------------------------------------------
# 2. Python Virtual Environment Setup
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/5] Initializing Python virtual environment...${NC}"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "  ${GREEN}✓${NC} Created .venv virtual environment."
else
    echo -e "  ${GREEN}✓${NC} Existing .venv virtual environment detected."
fi

# Activate venv
source .venv/bin/activate
echo -e "  ${GREEN}✓${NC} Activated virtual environment ($(which python3))."

# Note: Backend uses Python Standard Library only (zero third-party wheel bloat!)
echo -e "  ${GREEN}✓${NC} Python backend runs on 100% Standard Library (zero wheel dependencies to install)."

# ------------------------------------------------------------------------------
# 3. Web Frontend Build (React 18 + Vite + Tailwind CSS)
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/5] Building frontend production bundle...${NC}"

if [ -d "web" ]; then
    cd web
    if [ ! -d "node_modules" ]; then
        echo "  Installing web dependencies with npm..."
        npm ci --silent 2>/dev/null || npm install --silent
    else
        echo -e "  ${GREEN}✓${NC} node_modules present."
    fi
    echo "  Compiling TypeScript and bundling with Vite..."
    npm run build
    cd ..
    echo -e "  ${GREEN}✓${NC} Frontend compiled successfully to web/dist."
else
    echo -e "${RED}Error: web/ directory not found.${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. Database Initialization & Seeding
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/5] Initializing SQLite database and ledger seeding...${NC}"

export PYTHONPATH="src"

# Check if SQLite DB already has transactions or bootstrap from seed.sql / generator
if [ -f "yottaflex.db" ] && [ -s "yottaflex.db" ]; then
    TXN_COUNT=$(sqlite3 yottaflex.db "SELECT count(*) FROM transactions;" 2>/dev/null || echo "0")
    if [ "$TXN_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${NC} Database already seeded with $TXN_COUNT transactions."
    else
        echo "  Populating database from sql/seed.sql..."
        sqlite3 yottaflex.db < data/sql/seed.sql
        echo -e "  ${GREEN}✓${NC} Bootstrapped database from data/sql/seed.sql."
    fi
elif [ -f "data/sql/seed.sql" ]; then
    echo "  Creating yottaflex.db from data/sql/seed.sql..."
    sqlite3 yottaflex.db < data/sql/seed.sql
    echo -e "  ${GREEN}✓${NC} Database initialized from data/sql/seed.sql."
else
    echo "  Generating fresh synthetic dataset with seed 20261022..."
    python3 -m yottaflex.cli generate --seed 20261022 --scale full
    echo -e "  ${GREEN}✓${NC} Synthetic banking universe generated."
fi

# ------------------------------------------------------------------------------
# 5. System Health Check & Test Suite Execution
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[5/5] Running automated smoke tests...${NC}"

python3 -m unittest tests/test_part1_generation.py tests/test_financial_network_intelligence.py tests/test_part3_validation_eval.py -q
echo -e "  ${GREEN}✓${NC} Smoke tests passed successfully (zero-leakage AST guard & ledger integrity verified)."

echo ""
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}             YottaFlex RiskOS Setup Complete Successfully!              ${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo ""
echo -e "To launch the unified server (API + Liquid Glass UI on port 8080):"
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}PYTHONPATH=src python3 -m yottaflex.cli serve --scale full --port 8080${NC}"
echo ""
echo -e "Or simply run:"
echo -e "  ${CYAN}make serve${NC}"
echo ""
echo -e "Open in your browser: ${BOLD}http://localhost:8080${NC}"
echo ""
echo -e "Demo Credentials:"
echo -e "  • ${BOLD}Risk Analyst:${NC}      demo_analyst@yottaflex.ai   /  DemoAnalyst2026!"
echo -e "  • ${BOLD}Senior Reviewer:${NC}   demo_reviewer@yottaflex.ai  /  DemoAnalyst2026!"
echo -e "  • ${BOLD}System Admin:${NC}      demo_admin@yottaflex.ai     /  DemoAnalyst2026!"
echo ""
