# Multi-stage Dockerfile for Vue.js EASM Frontend

# Stage 1: Development
FROM node:20-alpine AS development

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Run dev server with hot reload
CMD ["npm", "run", "dev"]


# Stage 2: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build for production
RUN npm run build


# Stage 3: Production
FROM nginx:alpine AS production

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
