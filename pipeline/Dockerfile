FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements/project files
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling beautifulsoup4 lxml && \
    pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p data/vault data/atlas data/events data/sources data/pages

# Command to keep the container running
CMD ["tail", "-f", "/dev/null"]
