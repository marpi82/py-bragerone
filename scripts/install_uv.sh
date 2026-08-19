# shellcheck shell=bash
# Shared helper: install a hash-pinned uv release binary from GitHub.
#
# Bump procedure:
#   1. Pick a tag from https://github.com/astral-sh/uv/releases
#   2. Download sha256.sum from that release
#   3. Update UV_VERSION and the hashes below for linux gnu x86_64 / aarch64
#
# Usage (from a repo checkout):
#   # shellcheck source=scripts/install_uv.sh
#   source "${ROOT_DIR}/scripts/install_uv.sh"
#   install_uv_pinned

UV_VERSION="${UV_VERSION:-0.12.3}"

# Official release digests for UV_VERSION (from release asset sha256.sum).
UV_SHA256_LINUX_X86_64_GNU="600cf9a742aca00d292673b16b5acffaa7b8c269a364ad0c2e79498dcb1fe101"
UV_SHA256_LINUX_AARCH64_GNU="bb66cb52e7b1823aed1183630d8d8e5c958840d584a4c55ec10a4cfc168dcca2"

install_uv_pinned() {
  local dest_dir="${1:-${HOME}/.local/bin}"
  local arch tarball expected tmpdir archive

  if command -v uv >/dev/null 2>&1; then
    echo "  uv already installed ($(uv --version | head -n1)); skipping pinned download"
    return 0
  fi

  arch="$(uname -m)"
  case "${arch}" in
    x86_64 | amd64)
      tarball="uv-x86_64-unknown-linux-gnu.tar.gz"
      expected="${UV_SHA256_LINUX_X86_64_GNU}"
      ;;
    aarch64 | arm64)
      tarball="uv-aarch64-unknown-linux-gnu.tar.gz"
      expected="${UV_SHA256_LINUX_AARCH64_GNU}"
      ;;
    *)
      echo "Unsupported architecture for pinned uv install: ${arch}" >&2
      echo "Install uv manually from https://github.com/astral-sh/uv/releases/tag/${UV_VERSION}" >&2
      return 1
      ;;
  esac

  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/${tarball}"
  echo "  Downloading uv ${UV_VERSION} (${tarball})..."
  if ! curl -fsSL \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/${tarball}" \
    -o "${archive}"; then
    rm -rf "${tmpdir}"
    return 1
  fi

  echo "  Verifying SHA256..."
  if ! echo "${expected}  ${archive}" | sha256sum -c -; then
    rm -rf "${tmpdir}"
    return 1
  fi

  mkdir -p "${dest_dir}"
  tar -xzf "${archive}" -C "${tmpdir}"

  local uv_bin="${tmpdir}/uv"
  local uvx_bin="${tmpdir}/uvx"
  if [[ ! -f "${uv_bin}" ]]; then
    # uv >= 0.12.x release tarballs ship binaries in a top-level arch directory.
    uv_bin="$(find "${tmpdir}" -maxdepth 2 -type f -name uv -print -quit)"
    uvx_bin="$(find "${tmpdir}" -maxdepth 2 -type f -name uvx -print -quit)"
  fi
  if [[ ! -f "${uv_bin}" ]]; then
    echo "uv binary not found after extracting ${tarball}" >&2
    rm -rf "${tmpdir}"
    return 1
  fi

  install -m 0755 "${uv_bin}" "${dest_dir}/uv"
  if [[ -n "${uvx_bin}" && -f "${uvx_bin}" ]]; then
    install -m 0755 "${uvx_bin}" "${dest_dir}/uvx"
  fi
  rm -rf "${tmpdir}"

  export PATH="${dest_dir}:${PATH}"
  command -v uv >/dev/null 2>&1 || {
    echo "uv binary installed to ${dest_dir} but not found on PATH" >&2
    return 1
  }
  echo "  ✅ uv $(uv --version | head -n1) installed to ${dest_dir} (SHA256 verified)"
}
