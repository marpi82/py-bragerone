# syntax=docker/dockerfile:1
FROM python:3.13-slim-trixie

ARG POETRY_VERSION=>=2.0.1
ARG PDV_VERSION=>=1.4.0  # poetry-dynamic-versioning

ENV DEBIAN_FRONTEND=noninteractive \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-venv python3-dev git curl nano iproute2 \
      build-essential pkg-config ca-certificates \
      libffi-dev libssl-dev libpq-dev libsqlite3-dev \
      bash-completion net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
      "poetry${POETRY_VERSION}" \
      "poetry-dynamic-versioning[plugin]${PDV_VERSION}"

WORKDIR /workspace
CMD ["bash"]
