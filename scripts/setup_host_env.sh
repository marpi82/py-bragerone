#!/bin/bash
# Setup script for py-bragerone development environment on host
# This script prepares system deps, installs uv via pipx, and syncs the project env
set -euo pipefail

echo "🚀 Setting up py-bragerone development environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# 1. Ensure we're on Debian/Ubuntu (script uses apt)
# ---------------------------------------------------------------------------
if ! command -v apt >/dev/null 2>&1; then
    echo "⚠️  This script targets Debian/Ubuntu systems. Adjust package commands for your distro."
fi

# ---------------------------------------------------------------------------
# 2. Install system dependencies
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing system dependencies...${NC}"
if ! command -v python3 >/dev/null 2>&1 || ! python3 -m pip --version >/dev/null 2>&1; then
    echo "  Installing python3-pip, python3-venv, python3-dev, build-essential..."
    sudo apt update
    sudo apt install -y python3-pip python3-venv python3-dev build-essential
else
    echo "  ✅ Python 3 tooling already installed"
fi

# ---------------------------------------------------------------------------
# 3. Install pipx for isolated CLI tools
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Ensuring pipx is available...${NC}"
if ! command -v pipx >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y pipx
    else
        python3 -m pip install --user pipx
        python3 -m pipx ensurepath
    fi
    echo "  ✅ pipx installed"
else
    echo "  ✅ pipx already present"
fi

# ---------------------------------------------------------------------------
# 3a. Install GitHub CLI (gh)
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing GitHub CLI (gh)...${NC}"
if ! command -v gh >/dev/null 2>&1; then
    if command -v apt >/dev/null 2>&1; then
        echo "  Installing gh via official repository..."
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
        sudo apt update
        sudo apt install -y gh
        echo "  ✅ GitHub CLI installed"
    else
        echo "  ⚠️  Cannot install gh automatically on this system. Please install manually."
    fi
else
    echo "  ✅ GitHub CLI already installed ($(gh --version | head -n1))"
fi

# ---------------------------------------------------------------------------
# 4. Add ~/.local/bin to PATH (pipx install location)
# ---------------------------------------------------------------------------
echo -e "${BLUE}🔧 Configuring PATH...${NC}"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  Adding ~/.local/bin to PATH in ~/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
    echo "  ✅ PATH updated (restart shell or run: source ~/.bashrc)"
else
    echo "  ✅ ~/.local/bin already on PATH"
fi

# ---------------------------------------------------------------------------
# 6. Install uv (dependency manager) via pipx
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing uv...${NC}"
if ! command -v uv >/dev/null 2>&1; then
    pipx install uv
    echo "  ✅ uv installed"
else
    echo "  ✅ uv already installed ($(uv --version | head -n1))"
fi

# ---------------------------------------------------------------------------
# 7. Recommend helpful environment defaults
# ---------------------------------------------------------------------------
echo -e "${BLUE}ℹ️  Setting recommended environment defaults...${NC}"
if ! grep -q "UV_PROJECT_ENVIRONMENT" "$HOME/.bashrc" 2>/dev/null; then
    echo 'export UV_PROJECT_ENVIRONMENT=".venv"' >> "$HOME/.bashrc"
    echo "  ✅ Added UV_PROJECT_ENVIRONMENT=.venv to ~/.bashrc"
fi
if ! grep -q "UV_LINK_MODE" "$HOME/.bashrc" 2>/dev/null; then
    echo 'export UV_LINK_MODE="copy"' >> "$HOME/.bashrc"
    echo "  ✅ Added UV_LINK_MODE=copy to ~/.bashrc (avoids hardlink warnings)"
fi
if ! grep -q "RUFF_NUM_THREADS" "$HOME/.bashrc" 2>/dev/null; then
    echo 'export RUFF_NUM_THREADS="1"' >> "$HOME/.bashrc"
    echo "  ✅ Added RUFF_NUM_THREADS=1 to ~/.bashrc (prevents thread limit issues)"
fi

# Make the env vars available in the current shell
export UV_PROJECT_ENVIRONMENT=".venv"
export UV_LINK_MODE="copy"
export RUFF_NUM_THREADS="1"

# ---------------------------------------------------------------------------
# 8. Sync project dependencies with uv
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Syncing project dependencies (uv sync)...${NC}"
uv sync --locked --group dev --group test --group docs
echo "  ✅ Dependencies installed into .venv/"

# ---------------------------------------------------------------------------
# 9. Install pre-commit hooks inside the project environment
# ---------------------------------------------------------------------------
echo -e "${BLUE}🪝 Installing pre-commit hooks...${NC}"
uv run --group dev pre-commit install
echo "  ✅ pre-commit hooks installed"

# ---------------------------------------------------------------------------
# 10. Verify setup
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Installed versions:"
echo "  Python:  $(python3 --version 2>/dev/null || python --version)"
echo "  uv:      $(uv --version | head -n1)"
echo "  Venv:    $(ls -la .venv/bin/python 2>/dev/null | awk '{print $NF}' || echo 'Not found')"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "  1. Restart your shell (source ~/.bashrc) to load the new env vars"
echo "  2. Reload VS Code window if it was open"
echo "  3. Use uv/poe tasks for day-to-day work"
echo ""
echo -e "${GREEN}🎉 You're ready to develop!${NC}"
echo ""
echo "Common commands:"
echo "  uv run --group test pytest            # Run tests"
echo "  uv run --group dev ruff check .       # Lint code"
echo "  uv run --group dev mypy               # Type check"
echo "  uv run --group dev poe <task>         # Run poe task"
echo "  pre-commit run --all-files            # Run all pre-commit hooks"
echo ""
echo -e "${YELLOW}Tip:${NC} After restarting the shell, the exported env vars suppress uv hardlink warnings and Ruff thread panics."
