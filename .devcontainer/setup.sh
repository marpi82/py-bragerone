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

# Install uv
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.cargo/bin:$PATH"

# Make uv available for vscode user
if [ -d "/home/vscode" ]; then
    cp -r /root/.cargo /home/vscode/.cargo || true
    chown -R vscode:vscode /home/vscode/.cargo || true
    echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> /home/vscode/.bashrc
    echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> /home/vscode/.zshrc
fi

# Sync dependencies
echo "📦 Syncing project dependencies..."
uv sync --locked --group dev --group test --group docs

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
uv run --group dev pre-commit install

# Set ownership to vscode user
if [ -d "/home/vscode" ]; then
    chown -R vscode:vscode .venv || true
fi

echo "✅ Devcontainer setup complete!"
echo ""
echo "Available commands:"
echo "  uv run --group test pytest            # Run tests"
echo "  uv run --group dev ruff check .       # Lint code"
echo "  uv run --group dev mypy               # Type check"
echo "  uv run --group dev poe <task>         # Run poe task"
echo "  uv run --group dev poe validate       # Full validation"
