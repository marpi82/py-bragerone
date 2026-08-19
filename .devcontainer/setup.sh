#!/bin/bash
# Devcontainer setup script for py-bragerone
set -euo pipefail

echo "🚀 Setting up py-bragerone devcontainer..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../scripts/install_uv.sh
source "${ROOT_DIR}/scripts/install_uv.sh"

# Install system dependencies (with sudo if running as non-root)
echo "📦 Installing system dependencies..."
if [ "$EUID" -ne 0 ]; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        git
else
    apt-get update
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        git
fi

# Install uv from a version+SHA256-pinned GitHub release (no curl|sh).
echo "📦 Installing uv (hash-pinned ${UV_VERSION})..."
install_uv_pinned "${HOME}/.local/bin"
export PATH="${HOME}/.local/bin:${PATH}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-.venv}"
export PRE_COMMIT_HOME="${PRE_COMMIT_HOME:-${ROOT_DIR}/.cache/pre-commit}"

# Fix permissions for mounted volumes (they may be owned by root)
echo "🔧 Fixing volume permissions..."
mkdir -p "${PRE_COMMIT_HOME}"
sudo chown -R vscode:vscode "${PRE_COMMIT_HOME}" 2>/dev/null || true
if [ -d "$HOME/.cache/uv" ]; then
    sudo chown -R vscode:vscode "$HOME/.cache/uv" 2>/dev/null || true
fi
if [ -d "${VIRTUAL_ENV:-$PWD/.venv}" ]; then
    sudo chown -R vscode:vscode "${VIRTUAL_ENV:-$PWD/.venv}" 2>/dev/null || true
fi

# Sync dependencies
echo "📦 Syncing project dependencies..."
uv sync --locked --group dev --group test --group docs

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run --group dev pre-commit install

# Add uv to shell profile if not already there
echo "🔧 Configuring shell environment..."
if ! grep -q '.local/bin' "$HOME/.zshrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
fi

echo "✅ Devcontainer setup complete!"
echo ""
echo "Available commands:"
echo "  uv run --group test pytest            # Run tests"
echo "  uv run --group dev ruff check .       # Lint code"
echo "  uv run --group dev mypy               # Type check"
echo "  uv run --group dev poe <task>         # Run poe task"
echo "  uv run --group dev poe validate       # Full validation"
