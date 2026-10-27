# AWS EKS Web CLI - Read & Diagnostic Portal

A lightweight, secure, browser-based CLI tool for AWS EKS (Elastic Kubernetes Service) that allows developers and DevOps teams to view, inspect, and troubleshoot resources across **any namespace**, while enforcing strict guardrails to prevent destructive commands (`kubectl delete`) and shell injection.

---

## 🎯 Key Design Highlights

* **Open Cluster-Wide Namespace Access:** Users can query resources in any namespace (`-n <namespace>`) or cluster-wide (`-A`, `--all-namespaces`) without artificial per-user namespace locks.
* **Deletion Guardrail:** Strictly blocks destructive commands like `kubectl delete` to prevent accidental or malicious resource deletion.
* **Shell-Injection Proof:** Commands are tokenized via `shlex` and executed with `shell=False`. Chained commands (`;`, `&&`, `|`, `>`, `` ` ``) and unauthorized flags are rejected at the gateway.
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
               │  1. Receives Request (Any namespace allowed)                                │
               │                                                                             │
               │  2. Security Guardrail & Sanitizer:                                         │
               │     • 🚫 BLOCKS 'kubectl delete ...'                                        │
               │     • 🚫 BLOCKS ';', '&&', '|', '>', '`' (Shell Injection)                  │
               │     • 🚫 BLOCKS credential-tampering flags (--kubeconfig, --token)          │
               │     • ✅ ALLOWS 'get', 'describe', 'logs', 'top', 'explain', etc.           │
               │     • ✅ ALLOWS '-n <any-namespace>' and '-A' / '--all-namespaces'          │
               │                                                                             │
               │  3. Audit Logger (CloudWatch + UI Buffer)                                   │
               └─────────────────────────────────────────────────────────────────────────────┘
                                                              ▲
                                                              │ REST API (/api/v1/cli/exec)
                                                              │
               ┌──────────────────────────────────────────────┴──────────────────────────────┐
               │                        WEB CLI FRONTEND UI                                  │
               │  • Open Namespace Selector (Target any namespace or -A)                     │
               │  • Interactive Terminal (history, auto-scroll, colorized badges)            │
               │  • Quick Run Chips: [ get services ] [ get pods ] [ get pods -A ]           │
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
│   │   ├── config.py         # Config, suggested namespaces, guardrails
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
    │   └── web-cli-deployment.yaml # K8s manifests (Backend + Frontend)
    └── helm/                 # Production Helm chart
        ├── Chart.yaml
        ├── values.yaml       # Helm values
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

## 🛡️ Guardrail Rules

| Category | Policy | Examples |
| :--- | :--- | :--- |
| **Namespaces** | **Open** | Any namespace (`-n <ns>`, `-A`, `--all-namespaces`) is allowed. |
| **Inspection Actions** | **Allowed** | `get`, `describe`, `logs`, `top`, `explain`, `version`, `cluster-info` |
| **Destructive Actions** | **Blocked** | `kubectl delete ...`, `k delete ...` are strictly rejected. |
| **Shell Injection** | **Blocked** | `;`, `&&`, `\|`, `>`, `<`, `` ` ``, `$()`, `eval` are rejected. |
| **Credential Tampering** | **Blocked** | `--kubeconfig`, `--token`, `--as`, `--server` are rejected. |

---

## 🐳 Docker Build

### Build Backend Container:
```bash
docker build -t eks-web-cli-backend:latest -f backend/Dockerfile backend/
```

### Build Frontend Container:
```bash
docker build -t eks-web-cli-frontend:latest -f frontend/Dockerfile frontend/
```

---

## ☸ Deployment on AWS EKS

### Option A: Using the Helm Chart (Recommended)
```bash
helm upgrade --install eks-web-cli ./deploy/helm \
  --namespace ns-4 \
  --create-namespace \
  --set backend.image.repository="<your-registry>/eks-web-cli-backend" \
  --set backend.image.tag="latest" \
  --set frontend.image.repository="<your-registry>/eks-web-cli-frontend" \
  --set frontend.image.tag="latest"
```

### Option B: Using Kubernetes YAML Manifests
```bash
kubectl apply -f deploy/kubernetes/web-cli-deployment.yaml
```
