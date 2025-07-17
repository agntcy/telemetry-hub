# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

FROM python:3.13-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN pip install uv
# COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project --package metrics-computation-engine --no-install-workspace

# Copy code into builder
COPY . /src
WORKDIR /src

# Install just the mce-server package
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev --no-editable --package metrics-computation-engine

FROM python:3.13-slim-bookworm AS mce-release

RUN useradd -m user

COPY --from=builder --chown=user:user /app /app

USER user

# Set a working directory the user owns and can write to
WORKDIR /home/user/app

# Optional: copy your app source code here if needed
# COPY --chown=user:user . .

CMD ["/app/bin/mce-server"]
