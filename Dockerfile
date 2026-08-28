# ==============================================================================
# LumièreShop Container Image for Google Cloud Run
# ==============================================================================
# Base Image: Lightweight official Python 3.11 slim Debian distribution
FROM python:3.11-slim

# Set primary container working directory
WORKDIR /app

# Configure Python runtime:
# - PYTHONDONTWRITEBYTECODE: Prevents creation of transient .pyc cache files
# - PYTHONUNBUFFERED: Ensures application logs stream immediately to Cloud Logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Layer Caching: Install Python dependencies first before copying full codebase
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source code and static web assets (/static/index.html)
COPY backend /app/backend

# Switch working directory to the backend application root
WORKDIR /app/backend

# Default listening port configured for Google Cloud Run container contracts (8080)
ENV PORT=8080

EXPOSE 8080

# Launch Uvicorn ASGI server hosting the FastAPI application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
