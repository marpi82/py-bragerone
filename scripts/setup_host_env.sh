#!/bin/bash
# Setup script for py-bragerone development environment on host
# Prepares system deps, installs hash-pinned uv, and syncs the project env.
set -euo pipefail

echo "🚀 Setting up py-bragerone development environment..."
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/install_uv.sh
source "${ROOT_DIR}/scripts/lib/install_uv.sh"

# Pinned digest of https://cli.github.com/packages/githubcli-archive-keyring.gpg
# Bump when GitHub rotates the apt keyring.
GH_CLI_KEYRING_SHA256="6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b"

# ---------------------------------------------------------------------------
# 1. Ensure we're on Debian/Ubuntu (script uses apt)
# ---------------------------------------------------------------------------
if ! command -v apt >/dev/null 2>&1; then
    echo "⚠️  This script targets Debian/Ubuntu systems. Adjust package commands for your distro."
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Install system dependencies
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing system dependencies...${NC}"
if ! command -v python3 >/dev/null 2>&1 || ! python3 -m pip --version >/dev/null 2>&1; then
    echo "  Installing python3-pip, python3-venv, python3-dev, build-essential..."
    sudo apt update
    sudo apt install -y python3-pip python3-venv python3-dev build-essential curl ca-certificates
else
    echo "  ✅ Python 3 tooling already installed"
    sudo apt install -y curl ca-certificates >/dev/null
fi

# ---------------------------------------------------------------------------
# 3. Install GitHub CLI (gh) with a hash-verified apt keyring
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing GitHub CLI (gh)...${NC}"
if ! command -v gh >/dev/null 2>&1; then
    echo "  Installing gh via official repository (keyring SHA256-verified)..."
    tmp_keyring="$(mktemp)"
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o "${tmp_keyring}"
    echo "${GH_CLI_KEYRING_SHA256}  ${tmp_keyring}" | sha256sum -c -
    sudo install -m 0644 "${tmp_keyring}" /usr/share/keyrings/githubcli-archive-keyring.gpg
    rm -f "${tmp_keyring}"
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    sudo apt update
    sudo apt install -y gh
    echo "  ✅ GitHub CLI installed"
else
    echo "  ✅ GitHub CLI already installed ($(gh --version | head -n1))"
fi

# ---------------------------------------------------------------------------
# 4. Add ~/.local/bin to PATH
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
# 5. Install uv from a version+SHA256-pinned GitHub release (no pipx / curl|sh)
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Installing uv (hash-pinned ${UV_VERSION})...${NC}"
install_uv_pinned "${HOME}/.local/bin"
export PATH="${HOME}/.local/bin:${PATH}"

# ---------------------------------------------------------------------------
# 6. Recommend helpful environment defaults
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
# 7. Sync project dependencies with uv
# ---------------------------------------------------------------------------
echo -e "${BLUE}📦 Syncing project dependencies (uv sync)...${NC}"
cd "${ROOT_DIR}"
uv sync --locked --group dev --group test --group docs
echo "  ✅ Dependencies installed into .venv/"

# ---------------------------------------------------------------------------
# 8. Install pre-commit hooks inside the project environment
# ---------------------------------------------------------------------------
echo -e "${BLUE}🪝 Installing pre-commit hooks...${NC}"
uv run --group dev pre-commit install
echo "  ✅ pre-commit hooks installed"

# ---------------------------------------------------------------------------
# 9. Verify setup
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
