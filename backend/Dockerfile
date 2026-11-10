# ==========================================
# Base Stage
# ==========================================
FROM python:3.11-bookworm as base

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install system dependencies (nmap for scanning, wkhtmltopdf for reports)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    nmap \
    iputils-ping \
    wkhtmltopdf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# ==========================================
# Development Stage
# ==========================================
FROM base as development

# Install all dependencies including dev tools
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# We don't copy the code here because docker-compose will mount it as a volume for hot-reloading.
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==========================================
# Production Stage
# ==========================================
FROM base as production

# Install only production dependencies
RUN pip install --upgrade pip && \
    pip install .

# Copy the application code into the container (baked into the image)
COPY . .

EXPOSE 8000
# Run Gunicorn with Uvicorn workers for high concurrency in production
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
