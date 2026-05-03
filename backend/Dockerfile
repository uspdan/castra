FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    # Phase 10: libyara build deps for the source-build fallback when
    # yara-python's manylinux wheel is unavailable for the runtime
    # platform/arch. The wheel covers x86_64+arm64 cpython 3.10–3.12;
    # these tools are a belt-and-braces guard for unusual builds.
    automake \
    autoconf \
    libtool \
    make \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repo root (see docker-compose.yml). We stage the
# in-repo bluerange-spec package first so pip can resolve the path
# dependency declared in backend/requirements.txt.
COPY packages/bluerange-spec /packages/bluerange-spec
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir /packages/bluerange-spec

COPY backend/ /app/

# Phase 8: install the backend as an editable package so the
# bluerange.validators entry-point group registered in
# backend/pyproject.toml is discoverable via importlib.metadata. The
# install picks up zero new runtime deps (those still come from
# requirements.txt above) — this step exists purely to register entry
# points.
RUN pip install --no-cache-dir -e /app

# Sprint 1: production containers boot through ``entrypoint.sh`` so
# alembic is the single source of truth for schema. The lifespan's
# ``init_db()`` skips ``Base.metadata.create_all`` when
# ``DB_MIGRATIONS_MANAGED_EXTERNALLY=1`` is set (the entrypoint sets it).
# The CMD remains for tooling that bypasses the entrypoint (``docker
# run --entrypoint=python image -c …`` etc.) and matches the legacy
# behaviour byte-for-byte.
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
