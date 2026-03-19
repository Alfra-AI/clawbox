FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY pyproject.toml .
COPY mvp/ mvp/

# Install the package
RUN pip install --no-cache-dir .

# Create non-root user
RUN useradd -m -u 1000 agentbox && chown -R agentbox:agentbox /app
USER agentbox

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Run the application
CMD ["uvicorn", "mvp.main:app", "--host", "0.0.0.0", "--port", "8000"]
