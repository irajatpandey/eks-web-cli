# EKS Web CLI - Frontend Service

A modern cloud-terminal user interface for interacting with AWS EKS services within authorized namespaces.

---

## 🛠️ Configuration

Configuration is located in `frontend/config.json` and `frontend/nginx.conf`:

* `frontend/config.json`: Runtime UI settings (cluster name, API base path, default namespace).
* `frontend/nginx.conf`: Web server configuration, gzip compression, security headers, and reverse proxy settings (`/api/` forwarding to backend).

---

## 🚀 Running Locally

You can serve the frontend with any static web server (such as Python `http.server`, Nginx, or Caddy):

```bash
cd frontend

# Using python simple server for local testing:
python3 -m http.server 3000
```

Open `http://localhost:3000` in your browser. (Ensure the backend is running on `http://localhost:8080`).

---

## 🐳 Building Container

```bash
# Build from the frontend directory
docker build -t eks-web-cli-frontend:latest -f Dockerfile .

# Run container
docker run -p 80:80 eks-web-cli-frontend:latest
```
