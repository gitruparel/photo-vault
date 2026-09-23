FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase and frontend
COPY backend /app/backend
COPY index.html /app/index.html
COPY preview.html /app/preview.html

ENV PYTHONPATH=/app/backend
ENV STORAGE_LOCAL_ROOT=/data/storage/images
ENV DATABASE_URL=sqlite:////data/storage/vault.db
ENV ALLOW_PUBLIC_GALLERY=true
ENV ENVIRONMENT=production

# Storage volume mount point
RUN mkdir -p /data/storage/images

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
