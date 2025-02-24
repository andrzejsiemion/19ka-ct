# ---- Stage 1: Build dependencies ----
FROM python:3.9-slim AS builder

WORKDIR /app

# Install dependencies needed for building
RUN apt-get update && apt-get install -y \
    python3-dev \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies in a temporary directory
RUN pip install --no-cache-dir --prefix=/install \
    adafruit-circuitpython-dht \
    adafruit-blinka \
    RPi.GPIO \
    influxdb-client \
    loguru

# ---- Stage 2: Final runtime container ----
FROM python:3.9-alpine

WORKDIR /app

# Install only minimal runtime dependencies
RUN apk add --no-cache libgpiod python3 py3-pip tzdata

# Set timezone (can be overridden with an environment variable)
ENV TZ=Europe/Berlin
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Disable output buffering so logs appear instantly
ENV PYTHONUNBUFFERED=1

# Create the data directory and set correct permissions
RUN mkdir -p /app/data && chmod 777 /app/data
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy the script
COPY read_temp.py .

# Set the default command
ENTRYPOINT ["python3", "/app/read_temp.py"]
