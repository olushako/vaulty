# Multi-stage build for frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build the application
RUN npm run build

# Main stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including Node.js for frontend server)
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server/ ./server/

# Copy built frontend from builder
COPY --from=frontend-builder /app/dist /app/frontend/dist

# Copy frontend package files and vite config for preview server
COPY frontend/package*.json /app/frontend/
COPY frontend/vite.config.ts /app/frontend/
# Install vite as it's needed for preview (even though it's a dev dependency)
RUN cd /app/frontend && npm ci --only=production && npm install vite --save-dev

# Copy startup script
COPY start-services.sh /app/start-services.sh
RUN chmod +x /app/start-services.sh

# Create necessary directories
RUN mkdir -p /app/server/data

# Expose ports for all services
EXPOSE 8000 9000 3000

# Start all services
CMD ["/app/start-services.sh"]

