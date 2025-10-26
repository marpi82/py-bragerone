#!/bin/bash
# Devcontainer setup script for py-bragerone
set -euo pipefail

echo "🚀 Setting up py-bragerone devcontainer..."

# Install system dependencies (with sudo if running as non-root)
echo "📦 Installing system dependencies..."
if [ "$EUID" -ne 0 ]; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        ca-certificates
else
    apt-get update
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        ca-certificates
fi

# Install uv for current user
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Fix permissions for mounted volumes (they may be owned by root)
echo "🔧 Fixing volume permissions..."
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
