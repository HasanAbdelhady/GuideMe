# Production Dockerfile optimized for Railway
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN ["apt-get", "update"]
RUN ["apt-get", "install", "-y", "--no-install-recommends", "graphviz", "curl"]
RUN ["apt-get", "clean"]
RUN ["rm", "-rf", "/var/lib/apt/lists/*"]

# Install Python dependencies
COPY requirements.txt .
RUN ["pip", "install", "--no-cache-dir", "-r", "requirements.txt"]

# Copy application code
COPY . .

# Make entrypoint executable
RUN ["chmod", "+x", "/app/entrypoint.sh"]

# Expose port (Railway will override with PORT env var)
EXPOSE 8000

# Health check (using curl instead of requests library)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run application via entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "chatgpt.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
