# Lightweight, production-ready Nginx container for EKS Web CLI Frontend
FROM nginx:1.25-alpine as production

WORKDIR /usr/share/nginx/html

# Remove default nginx welcome page
RUN rm -rf ./*

# Copy custom nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static assets (HTML, CSS, JS)
COPY frontend/index.html ./index.html
COPY frontend/css/ ./css/
COPY frontend/js/ ./js/

# Security: Ensure non-root ownership of nginx cache and pid directories
RUN touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
