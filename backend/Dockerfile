# Production Dockerfile for UK Wind Forecast Analytics FastAPI Backend
FROM python:3.11-slim

# Prevent Python from writing bytecode and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Create non-root system user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Install dependencies with pip cache disabled
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy backend source code
COPY main.py schemas.py /app/
COPY services/ /app/services/

# Secure file permissions
RUN chown -R appuser:appuser /app

# Switch to non-root execution user
USER appuser

EXPOSE 8000

# Container healthcheck using standard Python library (no curl needed in slim image)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + '${PORT}' + '/health')" || exit 1

# Start Uvicorn bound to dynamic $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
