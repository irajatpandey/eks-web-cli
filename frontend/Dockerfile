# Production Nginx container for EKS Web CLI Frontend
FROM nginx:1.25-alpine as production

WORKDIR /usr/share/nginx/html

# Remove default nginx welcome page
RUN rm -rf ./*

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static assets and configuration
COPY index.html ./index.html
COPY config.json ./config.json
COPY css/ ./css/
COPY js/ ./js/

# Security: Ensure non-root ownership of nginx cache, pid, and html directories
RUN touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d

EXPOSE 80

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
