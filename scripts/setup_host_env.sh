#!/bin/bash
# Setup script for py-bragerone development environment on host
# This script installs Poetry, configures it, and sets up the project dependencies
set -e

echo "🚀 Setting up py-bragerone development environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# 1. Check if we're on Debian/Ubuntu
# ============================================================================
if ! command -v apt &> /dev/null; then
    echo "⚠️  This script is designed for Debian/Ubuntu. Adjust package manager commands for other distros."
fi

# ============================================================================
# 2. Install system dependencies
# ============================================================================
echo -e "${BLUE}📦 Installing system dependencies...${NC}"
if ! command -v python3 &> /dev/null || ! python3 -m pip --version &> /dev/null; then
    echo "  Installing python3-pip, python3-venv, python3-dev..."
    sudo apt update
    sudo apt install -y python3-pip python3-venv python3-dev build-essential
else
    echo "  ✅ Python3 and pip already installed"
fi

# ============================================================================
# 3. Install pipx if not present
# ============================================================================
echo -e "${BLUE}📦 Installing pipx...${NC}"
if ! command -v pipx &> /dev/null; then
    if command -v apt &> /dev/null; then
        sudo apt install -y pipx
    else
        python3 -m pip install --user pipx
        python3 -m pipx ensurepath
    fi
    echo "  ✅ pipx installed"
else
    echo "  ✅ pipx already installed"
fi

# ============================================================================
# 4. Ensure python symlink exists (Poetry needs 'python' not just 'python3')
# ============================================================================
echo -e "${BLUE}🔗 Checking python symlink...${NC}"
if ! command -v python &> /dev/null; then
    echo "  Creating symlink: /usr/bin/python -> /usr/bin/python3"
    sudo ln -sf /usr/bin/python3 /usr/bin/python
    echo "  ✅ Symlink created"
else
    echo "  ✅ python command available"
fi

# ============================================================================
# 5. Install Poetry
# ============================================================================
echo -e "${BLUE}📦 Installing Poetry...${NC}"
if ! command -v poetry &> /dev/null; then
    # Use system pipx
    if command -v pipx &> /dev/null; then
        pipx install poetry
    else
        # Fallback to using ~/.local/bin/pipx
        ~/.local/bin/pipx install poetry || /usr/bin/pipx install poetry
    fi
    echo "  ✅ Poetry installed"
else
    echo "  ✅ Poetry already installed ($(poetry --version))"
fi

# ============================================================================
# 6. Add ~/.local/bin to PATH if not already there
# ============================================================================
echo -e "${BLUE}🔧 Configuring PATH...${NC}"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "  Adding ~/.local/bin to PATH in ~/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    export PATH="$HOME/.local/bin:$PATH"
    echo "  ✅ PATH updated (restart shell or run: source ~/.bashrc)"
else
    echo "  ✅ ~/.local/bin already in PATH"
fi

# ============================================================================
# 7. Install poetry-dynamic-versioning plugin
# ============================================================================
echo -e "${BLUE}📦 Installing poetry-dynamic-versioning plugin...${NC}"
if ! poetry self show plugins | grep -q "poetry-dynamic-versioning"; then
    poetry self add "poetry-dynamic-versioning[plugin]"
    echo "  ✅ poetry-dynamic-versioning installed"
else
    echo "  ✅ poetry-dynamic-versioning already installed"
fi

# ============================================================================
# 8. Install poetry-plugin-export
# ============================================================================
echo -e "${BLUE}📦 Installing poetry-plugin-export...${NC}"
if ! poetry self show plugins | grep -q "poetry-plugin-export"; then
    poetry self add poetry-plugin-export
    echo "  ✅ poetry-plugin-export installed"
else
    echo "  ✅ poetry-plugin-export already installed"
fi

# ============================================================================
# 9. Configure Poetry to use in-project virtualenvs
# ============================================================================
echo -e "${BLUE}🔧 Configuring Poetry...${NC}"
poetry config virtualenvs.in-project true
echo "  ✅ Configured: virtualenvs.in-project = true"

# ============================================================================
# 10. Remove old virtualenv if it exists outside the project
# ============================================================================
echo -e "${BLUE}🧹 Cleaning up old virtualenvs...${NC}"
if [ -d "$HOME/.cache/pypoetry/virtualenvs" ]; then
    # Get project name from pyproject.toml
    PROJECT_NAME=$(grep '^name = ' pyproject.toml | head -1 | sed 's/name = "\(.*\)"/\1/')
    OLD_VENVS=$(find "$HOME/.cache/pypoetry/virtualenvs" -maxdepth 1 -type d -name "${PROJECT_NAME}*" 2>/dev/null || true)
    if [ -n "$OLD_VENVS" ]; then
        echo "  Removing old virtualenvs from Poetry cache..."
        poetry env remove python 2>/dev/null || true
        echo "  ✅ Old virtualenvs removed"
    else
        echo "  ✅ No old virtualenvs to clean"
    fi
else
    echo "  ✅ No Poetry cache directory found"
fi

# ============================================================================
# 11. Install project dependencies
# ============================================================================
echo -e "${BLUE}📦 Installing project dependencies...${NC}"
echo "  This may take a few minutes..."
poetry install --all-extras --with dev,test,docs
echo "  ✅ All dependencies installed in .venv/"

# ============================================================================
# 12. Install pre-commit hooks
# ============================================================================
echo -e "${BLUE}🪝 Installing pre-commit hooks...${NC}"
poetry run pre-commit install
echo "  ✅ Pre-commit hooks installed"

# ============================================================================
# 13. Verify installation
# ============================================================================
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Installed versions:"
echo "  Python:  $(python --version)"
echo "  Poetry:  $(poetry --version)"
echo "  Venv:    $(ls -la .venv/bin/python 2>/dev/null | awk '{print $NF}' || echo 'Not found')"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "  1. Reload VS Code window: Ctrl+Shift+P → 'Developer: Reload Window'"
echo "  2. Or restart your terminal: source ~/.bashrc"
echo "  3. New terminals will auto-activate .venv"
echo ""
echo -e "${GREEN}🎉 You're ready to develop!${NC}"
echo ""
echo "Common commands:"
echo "  poetry run pytest              # Run tests"
echo "  poetry run ruff check          # Lint code"
echo "  poetry run mypy src            # Type check"
echo "  poetry run poe <task>          # Run poe tasks"
echo "  pre-commit run --all-files     # Run all pre-commit hooks"
