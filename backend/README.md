# EKS Web CLI - Backend Service

A FastAPI-based REST API service that executes securely scoped `kubectl` commands against an AWS EKS cluster, enforcing strict namespace isolation and least-privilege access.

---

## 🛠️ Configuration

Configuration is managed via `backend/app/config.py` and can be overridden with environment variables:

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `JWT_SECRET_KEY` | _(dynamically generated if unset)_ | Secret key used to sign JWT authentication tokens. In production, configure via secure environment variable or secret manager. |
| `JWT_EXPIRATION_HOURS` | `8` | Lifetime of issued JWT tokens in hours. |
| `PORT` | `8080` | Port on which the FastAPI application listens. |
| `ALLOWED_NAMESPACES` | `ns-4,ns-5,ns-6,application-1,application-2,application-3,application-8,application-9` | Comma-separated list of managed cluster namespaces. |

---

## 🚀 Running Locally

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies from backend pyproject.toml
pip install -e ".[dev]"

# Run unit and security guardrail tests
pytest

# Start the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🐳 Building Container

```bash
# Build from the backend directory
docker build -t eks-web-cli-backend:latest -f Dockerfile .
```
