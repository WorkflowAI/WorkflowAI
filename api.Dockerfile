# Build stage
ARG PYTHON_VERSION=3.12
ARG ALPINE_VERSION=3.21
ARG ARCH=linux/amd64
ARG RELEASE_NAME=

FROM --platform=${ARCH} python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS python-base

# python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# ffmpeg is needed for audio processing
# poppler is needed for pdf processing
# Other upgrades are due for CVEs
RUN apk update && apk add --no-cache ffmpeg poppler-utils sqlite-libs>=3.48.0-r3 libexpat>=2.7.2-r0 \
    && apk upgrade --available --no-cache libssl3 libcrypto3 libxml2 xz-libs sqlite-libs

FROM python-base AS builder

WORKDIR /app

# Install build dependencies
# Remove 'geos-dev' if we stop using 'google-cloud-aiplatform'
RUN apk add --no-cache build-base libffi-dev geos-dev
# Update pip, install poetry setuptools, and wheel
# TODO: fetch version from pyproject.toml ?
RUN pip install --upgrade pip setuptools wheel poetry==2.1.3 poetry-plugin-export==1.9.0

# Copy the requirements file and install dependencies
ADD pyproject.toml poetry.lock ./

# A stage that installs the dependencies via poetry for development
FROM builder AS dev

RUN poetry install

# A stage that builds the wheels
FROM builder AS wheels

RUN poetry check --lock && poetry export --only main -f requirements.txt --output requirements.txt
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Production stage
FROM python-base

ARG RELEASE_NAME
ENV RELEASE_NAME=${RELEASE_NAME}
ENV SENTRY_RELEASE=${RELEASE_NAME}

WORKDIR /app

# Copy only the built wheels and installed packages from the wheels stage
COPY --from=wheels /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# Copy the rest of the application
COPY api/api api
COPY docsv2 docsv2
COPY api/core core
COPY api/start.sh /app/start.sh

ENV PATH="/app/.venv/bin:$PATH"

CMD ["/app/start.sh"]
