# ============================================================
# Frontend Dockerfile – Multi-Stage Build
# Vue 3 + Vite → Nginx
# ============================================================

# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ .
RUN npm run build

# --- Stage 2: Produktion mit Nginx ---
FROM nginx:alpine AS production

# Nginx-Konfiguration
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Vue-Build-Dateien
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
