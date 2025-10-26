# py-bragerone Devcontainer

This devcontainer provides a fully configured development environment for py-bragerone.

## Features

- **Base image**: `python:3.13-slim-trixie`
- **Dependency management**: uv
- **Build system**: Hatch with hatch-vcs (CalVer from git tags)
- **Pre-configured tools**: Ruff, mypy, pytest, Bandit, Semgrep, pip-audit
- **VS Code extensions**: Python, Pylance, Ruff, mypy-type-checker, GitLens, Copilot
- **NFS-optimized**: `.venv` and uv cache stored in Docker volumes (not on NFS mount)

## Quick Start

1. Open the project in VS Code
2. When prompted, click "Reopen in Container" (or press `F1` → `Dev Containers: Reopen in Container`)
3. Wait for the container to build and setup to complete
4. Start developing!

## Environment Variables

The following environment variables are pre-configured:

- `UV_PROJECT_ENVIRONMENT=.venv` - Use project-local virtualenv
- `UV_LINK_MODE=copy` - Avoid hardlink warnings
- `RUFF_NUM_THREADS=1` - Prevent thread limit issues

## Common Commands

```bash
# Run tests
uv run --group test pytest

# Lint and format
uv run --group dev poe fix

# Type check
uv run --group dev poe typecheck

# Full validation (quality + security + tests)
uv run --group dev poe validate

# Build documentation
uv run --group docs poe docs-build
uv run --group docs poe docs-serve

# Run pre-commit hooks manually
uv run --group dev pre-commit run --all-files
```

## Features Included

- Git with credential forwarding
- Zsh as default shell (with common-utils feature)
- User `vscode` with automatic UID/GID mapping
- Git config mounted from host

## Customization

To customize the devcontainer, edit `.devcontainer/devcontainer.json` and rebuild the container.

## Troubleshooting

### Permission Denied Errors

If you see `E: List directory /var/lib/apt/lists/partial is missing. - Acquire (13: Permission denied)`:
- The setup script now uses `sudo` automatically when running as non-root user
- Rebuild the container: `Dev Containers: Rebuild Container`

### Remote Extension Host Crashes

If you see `Remote Extension host terminated unexpectedly 3 times within the last 5 minutes`:
- This is fixed by adding `--init` flag to `runArgs` (prevents zombie processes)
- Rebuild the container to apply the fix

### Container build fails

Ensure Docker/Podman is running and you have internet connectivity.

### Permission issues with files

The container runs as user `vscode` (non-root). File ownership is automatically adjusted during setup.

### Missing extensions

Extensions are automatically installed. If missing, reload the window or rebuild the container.

### uv command not found

If `uv` is not found after setup:
- Reload the terminal or open a new one
- Check PATH: `echo $PATH` (should include `~/.local/bin`)
- Manually source: `source ~/.zshrc`

### NFS-related errors (Directory not empty)

If you see `failed to remove directory: Directory not empty (os error 39)`:
- This is an NFS issue with atomic operations
- **Solution**: `.venv` is now stored in a Docker volume (not NFS) via mounts configuration
- If you still see this after rebuild, clean volumes:
  ```bash
  docker volume rm py-bragerone-venv py-bragerone-uv-cache
  ```
- Then rebuild container
