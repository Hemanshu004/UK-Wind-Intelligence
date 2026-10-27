# Multi-stage Dockerfile for React 19 + Vite Frontend

# Stage 1: Build static distribution files
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests and install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy application source code
COPY . .

# Build-time environment variable for API base URL
# Default is empty string (""), enabling relative-path proxying through Nginx
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Compile production bundle into /app/dist
RUN npm run build

# Stage 2: Serve static bundle via lightweight Nginx web server
FROM nginx:alpine

# Copy custom Nginx configuration with reverse proxy rules
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Web server healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
