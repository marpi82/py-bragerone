#!/bin/bash
# Devcontainer setup script for py-bragerone
set -euo pipefail

echo "🚀 Setting up py-bragerone devcontainer..."

# Install system dependencies
echo "📦 Installing system dependencies..."
apt-get update
apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates

# Install uv globally
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"

# Make uv available system-wide
ln -sf /root/.local/bin/uv /usr/local/bin/uv || true

# Sync dependencies as root (will be accessible by vscode user)
echo "📦 Syncing project dependencies..."
uv sync --locked --group dev --group test --group docs

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run --group dev pre-commit install

# Fix ownership for vscode user
echo "🔧 Fixing permissions for vscode user..."
chown -R vscode:vscode .venv
chown -R vscode:vscode .git/hooks

echo "✅ Devcontainer setup complete!"
echo ""
echo "Available commands:"
echo "  uv run --group test pytest            # Run tests"
echo "  uv run --group dev ruff check .       # Lint code"
echo "  uv run --group dev mypy               # Type check"
echo "  uv run --group dev poe <task>         # Run poe task"
echo "  uv run --group dev poe validate       # Full validation"
