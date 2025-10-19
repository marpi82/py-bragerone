#!/bin/bash
set +x
set -e

echo "🚀 Setting up Python environment..."

# 🧩 Check Poetry
python -m poetry --version || true

# 🧹 Remove old venv if incompatible
if [ -f .venv/pyvenv.cfg ] && ! grep -q "/usr/local" .venv/pyvenv.cfg; then
  echo "🧹 Cleaning old virtual environment..."
  rm -rf .venv
fi

# ⚙️ Poetry configuration and installation
# (ignore errors to allow re-running the script)
echo "⚙️ Configuring Poetry and installing dependencies..."
poetry config virtualenvs.in-project true || true

# Try poetry install, if it fails with lock file error, regenerate lock and retry
if ! poetry install --all-extras --with dev,test,docs -n 2>&1; then
    echo "⚠️ Poetry install failed, checking if lock file needs updating..."
    if poetry install --all-extras --with dev,test,docs -n 2>&1 | grep -q "poetry.lock was last generated"; then
        echo "🔄 Regenerating poetry.lock file..."
        poetry lock
        echo "🔄 Retrying poetry install..."
        poetry install --all-extras --with dev,test,docs -n
    else
        echo "❌ Poetry install failed for unknown reason, continuing anyway..."
    fi
fi

# 🔍 Versions
python -V
poetry run ruff --version
poetry run mypy --version || true

echo "🧩 Installing Starship prompt..."
curl -fsSL https://starship.rs/install.sh | sh -s -- -y || true

# ✨ Shell and prompt settings
{
  echo "# === Starship prompt ==="
  echo 'eval "$(starship init bash)"'
  echo "# Auto-activate .venv if exists"
  echo 'if [ -d /workspace/.venv ] && [ -z "$VIRTUAL_ENV" ]; then source /workspace/.venv/bin/activate; fi'
} >> /etc/bash.bashrc

# 🎨 Starship configuration
mkdir -p /etc
cat >/etc/starship.toml <<'EOF'
add_newline = true
format = "$username@$hostname $directory$git_branch$git_status$python$cmd_duration$character"

[username]
show_always = true

[hostname]
ssh_only = false

[directory]
truncation_length = 3

[git_branch]
format = " [ $branch]($style)"
style = "yellow"

[git_status]
format = "[$all_status$ahead_behind]($style) "
style = "red"

[python]
format = " [ $virtualenv]($style)"
style = "purple"
EOF

echo "✅ Devcontainer setup finished!"
