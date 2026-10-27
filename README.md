# AWS EKS Web CLI - Scoped Access Portal

A lightweight, secure, web-based CLI tool for AWS EKS (Elastic Kubernetes Service) that allows developers and DevOps teams to view and manage services and resources **strictly within their assigned namespaces** without requiring admin privileges or creating complex multi-tenant RoleBindings.

---

## 🎯 Key Design Highlights

* **Pure Application-Level Namespace Isolation:** Uses the pod's existing automounted ServiceAccount token (`automountServiceAccountToken: true`). Zero extra Kubernetes Role/RoleBinding manifests needed.
* **Namespace Lockdown:** If a user is assigned to `ns-4`, they can **only** see resources in `ns-4`. Cross-namespace access (`-n ns-5`) and cluster-wide queries (`-A`, `--all-namespaces`) are blocked at the gateway.
* **Shell-Injection Proof:** Commands are safely tokenized via `shlex` and executed with `shell=False`. Chained commands (`;`, `&&`, `|`, `>`, `` ` ``) are rejected.
* **Modern Cloud Terminal UI:** Features an interactive web CLI with syntax-highlighted tables, command history (Up/Down arrows), quick action chips, and a visual service cards view.
* **Comprehensive Audit Trail:** Logs every command, user identity, namespace, latency, and status (`SUCCESS` / `BLOCKED`) to stdout (captured by Amazon CloudWatch) and a live UI drawer.

---

## 🏗️ Architecture

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │                     AWS EKS CLUSTER                    │
                                  └────────────────────────────────────────────────────────┘
                                                              ▲
                                                              │ (Automounted Pod Token)
                                                              │
               ┌──────────────────────────────────────────────┴──────────────────────────────┐
               │                        WEB CLI BACKEND POD                                  │
               │                                                                             │
               │  1. Authenticates User (JWT / SSO)                                          │
               │  2. Resolves Allowed Namespaces:                                            │
               │     • Alice   ──► ["ns-4"]                                                  │
               │     • Bob     ──► ["application-1"]                                         │
               │     • Carol   ──► ["ns-5", "ns-6"]                                          │
               │                                                                             │
               │  3. Command Guardrail & Sanitizer:                                          │
               │     • Blocks `-A`, `--all-namespaces`                                       │
               │     • Blocks `;`, `&&`, `|`, `>`                                            │
               │     • Forces `--namespace=<allowed_ns>`                                     │
               │                                                                             │
               │  4. Audit Logger (CloudWatch + UI Buffer)                                   │
               └─────────────────────────────────────────────────────────────────────────────┘
                                                              ▲
                                                              │ REST API (/api/v1/cli/exec)
                                                              │
               ┌──────────────────────────────────────────────┴──────────────────────────────┐
               │                        WEB CLI FRONTEND UI                                  │
               │  • Namespace Selector (shows only user's authorized namespaces)             │
               │  • Interactive Terminal (history, auto-scroll, colorized badges)            │
               │  • Quick Run Chips: [ get services ] [ get pods ] [ get endpoints ]         │
               │  • Visual Service Grid Tab                                                  │
               │  • Real-time Audit Drawer                                                   │
               └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```text
eks-web-cli/
├── backend/                  # 🐍 Backend Service (Python FastAPI + Scoped kubectl)
│   ├── pyproject.toml        # Backend's own PEP 621 packaging & dependencies
│   ├── Dockerfile            # Backend's own container build configuration
│   ├── README.md             # Backend local setup & guide
│   ├── app/                  # Application source code
│   │   ├── config.py         # Config, namespaces list, user map, RBAC whitelist
│   │   ├── auth.py           # JWT authentication and user context
│   │   ├── executor.py       # Command parser, sanitizer, and kubectl runner
│   │   ├── audit.py          # CloudWatch & in-memory audit log stream
│   │   └── main.py           # FastAPI application entrypoint
│   └── tests/                # Backend unit & security guardrail tests
│       ├── test_security_guardrails.py
│       └── test_api.py
├── frontend/                 # 🌐 Frontend Service (Nginx Alpine + Web CLI Portal)
│   ├── Dockerfile            # Frontend's own container build configuration
│   ├── nginx.conf            # Nginx reverse proxy configuration & security headers
│   ├── config.json           # Frontend runtime UI configuration
│   ├── README.md             # Frontend local setup & guide
│   ├── index.html            # Semantic HTML5 terminal interface
│   ├── css/
│   │   └── style.css         # Modern dark-theme design system
│   └── js/
│       └── app.js            # Terminal interaction, namespace selector, audit drawer
└── deploy/                   # ☸ Deployment Configuration
    ├── backend.Dockerfile    # Centralized backend container build file
    ├── frontend.Dockerfile   # Centralized frontend container build file
    ├── kubernetes/
    │   └── web-cli-deployment.yaml # Decoupled K8s manifests (Backend + Frontend)
    └── helm/                 # Production Helm chart
        ├── Chart.yaml
        ├── values.yaml       # Decoupled backend and frontend values
        └── templates/
            ├── deployment-backend.yaml
            ├── deployment-frontend.yaml
            ├── service-backend.yaml
            ├── service-frontend.yaml
            └── ingress.yaml
```

---

## 🚀 Quick Start (Local Development)

### 1. Running the Backend
```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies from backend's pyproject.toml
pip install -e ".[dev]"

# Run tests
pytest

# Start the backend server
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Running the Frontend
```bash
cd frontend

# Run static web server
python3 -m http.server 3000
```
Open your browser at **http://localhost:3000** to access the Web CLI.

---

## 🛡️ Pre-configured Test Accounts

| Username | Role | Allowed Namespaces |
| :--- | :--- | :--- |
| **alice** | Developer | `ns-4` |
| **bob** | Payments Team | `application-1` |
| **carol** | Analytics Team | `ns-5`, `ns-6` |
| **dave** | Billing Team | `application-2`, `application-3` |
| **qa-user** | QA Engineer | `application-8`, `application-9` |
| **devops-viewer** | DevOps Viewer | All Namespaces |

---

## 🐳 Docker Build

### Build Backend Container (inside `backend/`):
```bash
cd backend
docker build -t eks-web-cli-backend:latest .
```

### Build Frontend Container (inside `frontend/`):
```bash
cd frontend
docker build -t eks-web-cli-frontend:latest .
```

---

## ☸ Deployment on AWS EKS

### Option A: Using the Helm Chart (Recommended)
```bash
helm upgrade --install eks-web-cli ./deploy/helm \
  --namespace web-cli-system \
  --create-namespace \
  --set image.repository="<your-aws-account-id>.dkr.ecr.us-east-1.amazonaws.com/eks-web-cli" \
  --set image.tag="latest"
```

### Option B: Using Kubernetes YAML Manifests
```bash
kubectl apply -f deploy/kubernetes/web-cli-deployment.yaml
```
