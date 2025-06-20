# Use Ubuntu 24.04 as base image
FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/root/.local/bin:/root/.cargo/bin:$PATH"
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VENV_IN_PROJECT=1
ENV POETRY_CACHE_DIR=/tmp/poetry_cache

# Update package list and install system dependencies
RUN apt-get update && apt-get install -y \
    # Essential system packages
    curl \
    wget \
    git \
    build-essential \
    software-properties-common \
    ca-certificates \
    gnupg \
    lsb-release \
    # Python build dependencies
    python3-dev \
    python3-pip \
    python3-venv \
    # Media processing libraries (for poppler and ffmpeg tests)
    poppler-utils \
    ffmpeg \
    # Additional libraries that might be needed for Python packages
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    zlib1g-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Install Python 3.12 specifically
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y python3.12 python3.12-dev python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python3.12 to be the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# Install pipx and Poetry
RUN python3 -m pip install --user pipx \
    && pipx install poetry==2.1.3

# Install Node.js 21
RUN curl -fsSL https://deb.nodesource.com/setup_21.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Yarn (using npm to get the latest version, then configure for v4.1.0)
RUN npm install -g yarn \
    && yarn set version 4.1.0

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . ~/.cargo/env

# Verify installations
RUN python3 --version \
    && poetry --version \
    && node --version \
    && yarn --version \
    && rustc --version \
    && cargo --version

# Set working directory
WORKDIR /workspace

# Configure Poetry to create virtual environments in project
RUN poetry config virtualenvs.in-project true

# Pre-create poetry cache directory
RUN mkdir -p $POETRY_CACHE_DIR

# Default command
CMD ["/bin/bash"]