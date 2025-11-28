# Core Platform - Session Memory & Documentation

## 📋 Overview
**Component**: Core Platform (Backend, Database, Admin Frontend)
**Purpose**: Main control plane for agentless Kubernetes cost optimization (CAST AI competitor)
**Architecture**: Agentless (EventBridge + SQS + Remote Kubernetes API)
**Instance Type**: Primary server (handles all core logic)
**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 📝 Change Tracking & Cross-Component Coordination

**IMPORTANT**: This component is part of a multi-component system. Changes here may affect other components.

### Common Changes Log
**Location**: `new app/common/CHANGES.md`

**Purpose**: Track all changes that affect multiple components (ML Server, Core Platform, Frontend)

**When to Check**:
- ✅ **Before starting work**: Read CHANGES.md to understand recent cross-component updates
- ✅ **After completing work**: Log any change that affects other components
- ✅ **During API changes**: Always update CHANGES.md if you modify request/response schemas

**When to Update CHANGES.md**:
- API contract changes (endpoints, schemas)
- AWS IAM permission changes
- Kubernetes RBAC changes
- Environment variable changes
- Dependency version updates
- Security changes
- Breaking changes to any interface
- Data collection changes that affect ML Server inputs

**Developer Workflow**:
```bash
# Before starting
cat "new app/common/CHANGES.md"                 # Check recent changes
cat "new app/core-platform/SESSION_MEMORY.md"   # Check component-specific memory

# After completing work
vim "new app/core-platform/SESSION_MEMORY.md"   # Update component memory
vim "new app/common/CHANGES.md"                 # Log cross-component changes
git commit -m "Core Platform: Descriptive message"
```

**Cross-Component Dependencies**:
- **Core Platform → ML Server**: Data collection format must match ML Server decision engine inputs
- **Core Platform → Frontend**: API responses must match frontend TypeScript interfaces
- **AWS/K8s Changes**: IAM/RBAC changes affect customer onboarding process

---

## 🎯 Core Responsibilities

### 1. Central Database Management
- PostgreSQL database with all customer and cluster data
- Time-series metrics storage
- State management for all clusters
- Historical optimization records
- Customer configuration and billing data

### 2. Agentless Cluster Management
- **Remote Kubernetes API Access** - Direct API calls to customer clusters (no agents)
- **AWS EventBridge + SQS Polling** - Receive Spot interruption warnings
- **AWS EC2 API** - Launch/terminate instances, query Spot prices
- **No DaemonSets** - Zero footprint in customer clusters

### 3. API & Orchestration
- Main REST API for all operations
- **Coordinates with ML Server for ALL decisions** (Core Platform does NOT make optimization decisions)
- Executes optimization plans remotely (receives plans from ML Server)
- Handles AWS API interactions (EC2, SQS, EventBridge)
- Remote Kubernetes API interactions
- **Architecture**: Core Platform collects data → ML Server makes decisions → Core Platform executes

### 4. Admin Frontend
- Real-time cost monitoring dashboard
- Live comparison: predictions vs actual data
- Model upload and management interface
- Customer configuration UI
- Optimization history and analytics
- Gap filling tool UI

### 5. Decision Execution Engine
- **Receives ALL recommendations from ML Server** (no local decision logic)
- Validates safety checks before execution
- Executes optimization plans via remote K8s API + AWS EC2 API
- Handles rollback scenarios
- Monitors execution status
- **Key**: Core Platform is the "executor", ML Server is the "brain"

### 6. Event Processing (Agentless)
- **SQS Queue Polling** for Spot interruption warnings (every 5 seconds)
- **EventBridge Event Routing** from customer AWS accounts
- Real-time cluster state updates via remote K8s API
- Webhook notifications (Slack, email)

---

## 🔌 Integration Points (Agentless Architecture)

### A. Communication with ML Server
**Protocol**: REST API + WebSocket
**Direction**: Core Platform → ML Server (request/response)

**Endpoints Called on ML Server**:
- `POST /api/v1/ml/decision/spot-optimize` - Get Spot instance recommendations
- `POST /api/v1/ml/decision/bin-pack` - Get consolidation plan
- `POST /api/v1/ml/decision/rightsize` - Get rightsizing recommendations
- `POST /api/v1/ml/predict/spot-interruption` - Get interruption probability

**Data Flow**:
```
Core Platform → ML Server: Decision request (cluster state + requirements)
ML Server → Core Platform: Recommendations + execution plan
Core Platform: Validates and executes plan via remote K8s API
Core Platform: Stores results in database
```

### B. Remote Kubernetes API Integration (NO AGENTS)
**Protocol**: HTTPS to customer Kubernetes API server
**Authentication**: Service Account Token (provided by customer)

**Endpoints Called on Customer K8s API**:
```
GET  /api/v1/nodes                              - List cluster nodes
GET  /api/v1/pods                               - List all pods
GET  /apis/metrics.k8s.io/v1beta1/nodes        - Get node metrics
GET  /apis/metrics.k8s.io/v1beta1/pods         - Get pod metrics
POST /api/v1/namespaces/{ns}/pods/{pod}/eviction  - Evict pod (drain)
PATCH /api/v1/nodes/{name}                      - Cordon/uncordon node
PATCH /apis/apps/v1/namespaces/{ns}/deployments/{name}  - Update deployment
```

**RBAC Required in Customer Cluster**:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cloudoptim
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cloudoptim
rules:
  - apiGroups: [""]
    resources: ["nodes", "pods", "persistentvolumeclaims"]
    verbs: ["get", "list", "watch", "patch"]
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets"]
    verbs: ["get", "list", "patch"]
  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods/eviction"]
    verbs: ["create"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cloudoptim
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cloudoptim
subjects:
  - kind: ServiceAccount
    name: cloudoptim
    namespace: kube-system
```

**Data Flow**:
```
Core Platform → Customer K8s API: List nodes, get metrics
Core Platform: Analyze cluster state
Core Platform → ML Server: Request optimization decisions
ML Server → Core Platform: Recommendations
Core Platform → Customer K8s API: Execute optimization (drain, cordon, etc.)
Core Platform → AWS EC2 API: Launch/terminate instances
```

### C. AWS EventBridge + SQS Integration
**Purpose**: Receive Spot instance interruption warnings (2-minute notice)

**Customer Setup**:
1. Create EventBridge rule in customer AWS account:
```json
{
  "source": ["aws.ec2"],
  "detail-type": ["EC2 Spot Instance Interruption Warning"],
  "detail": {
    "instance-id": [{"prefix": ""}]
  }
}
```

2. Create SQS queue: `cloudoptim-spot-warnings-{customer_id}`

3. EventBridge rule targets SQS queue

**Core Platform Polling**:
- Poll SQS queue every 5 seconds
- Receive Spot interruption warnings
- Process event within 2 minutes (before termination)
- Drain node via remote K8s API
- Launch replacement instance via EC2 API

**SQS Message Format**:
```json
{
  "version": "0",
  "id": "12345",
  "detail-type": "EC2 Spot Instance Interruption Warning",
  "source": "aws.ec2",
  "time": "2025-11-28T10:00:00Z",
  "detail": {
    "instance-id": "i-1234567890abcdef0",
    "instance-action": "terminate"
  }
}
```

### D. AWS EC2 API Integration
**Protocol**: AWS SDK (boto3)
**Authentication**: IAM Role (cross-account assume role)

**Operations**:
- `RunInstances` - Launch new Spot/On-Demand instances
- `TerminateInstances` - Terminate old instances
- `DescribeInstances` - Query instance details
- `DescribeSpotPriceHistory` - Get historical Spot prices
- `CreateTags` - Tag instances with cluster info

**IAM Permissions Required**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeInstances",
        "ec2:DescribeSpotPriceHistory",
        "ec2:CreateTags"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:cloudoptim-*"
    }
  ]
}
```

### E. Shared Data Schemas (COMMON)
**Location**: `/common/schemas/` (shared with ML Server)

```python
# Common data models
class ClusterState(BaseModel):
    cluster_id: str
    node_count: int
    total_cpu: float
    total_memory: float
    pod_count: int
    spot_node_count: int
    on_demand_node_count: int
    current_cost_per_hour: float

class DecisionRequest(BaseModel):
    request_id: str
    cluster_id: str
    decision_type: str  # spot_optimize, bin_pack, rightsize
    requirements: Dict[str, Any]
    constraints: Dict[str, Any]

class RemoteK8sTask(BaseModel):
    task_id: str
    cluster_id: str
    task_type: str  # drain_node, cordon_node, scale_deployment
    parameters: Dict[str, Any]
    priority: int
    deadline: datetime
```

---

## 📁 Directory Structure

```
core-platform/
├── SESSION_MEMORY.md          # This file
├── README.md
├── requirements.txt
├── config/
│   ├── common.yaml            # Shared with ML Server
│   ├── database.yaml          # Database configuration
│   └── aws.yaml               # AWS configuration
├── api/
│   ├── main.py                # FastAPI application
│   ├── routes/
│   │   ├── customers.py       # Customer management
│   │   ├── clusters.py        # Cluster management
│   │   ├── optimization.py    # Optimization endpoints
│   │   ├── ml_proxy.py        # Proxy to ML Server
│   │   ├── events.py          # EventBridge/SQS endpoints
│   │   └── admin.py           # Admin endpoints
│   ├── middleware/
│   │   ├── auth.py
│   │   └── rate_limit.py
│   └── dependencies/
│       ├── database.py
│       └── aws.py
├── database/
│   ├── migrations/            # Alembic migrations
│   ├── models.py              # SQLAlchemy models
│   ├── schemas.py             # Pydantic schemas
│   └── seed_data.sql          # Initial data
├── services/
│   ├── optimizer_service.py   # Orchestrates optimization (calls ML Server)
│   ├── executor_service.py    # Executes optimization plans from ML Server
│   ├── spot_handler.py        # Handles Spot interruptions
│   ├── k8s_remote_client.py   # Remote Kubernetes API client (NO AGENT)
│   ├── eventbridge_poller.py  # SQS poller for Spot warnings
│   ├── aws_client.py          # AWS EC2 API client
│   ├── ml_client.py           # ML Server client (sends requests, receives decisions)
│   ├── metrics_collector.py   # Collects cluster metrics via remote K8s API
│   ├── data_collector.py      # Collects EC2/EBS data for ML Server analysis
├── admin-frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx          # Main dashboard
│   │   │   ├── CostMonitor.tsx        # Real-time cost display
│   │   │   ├── PredictionComparison.tsx # Predictions vs actual
│   │   │   ├── ModelUploader.tsx      # Upload ML models
│   │   │   ├── GapFiller.tsx          # Data gap filling UI
│   │   │   ├── ClusterList.tsx
│   │   │   └── OptimizationHistory.tsx
│   │   ├── services/
│   │   │   └── api.ts             # API client
│   │   └── types/
│   │       └── index.ts           # TypeScript types
│   └── public/
├── scripts/
│   ├── install.sh             # Installation script
│   ├── setup_database.sh      # Database setup
│   ├── migrate_database.sh    # Run migrations
│   └── start_server.sh        # Start server
├── tests/
│   ├── test_api.py
│   ├── test_services.py
│   ├── test_k8s_client.py
│   └── test_eventbridge.py
└── docs/
    ├── API_SPEC.md
    ├── DEPLOYMENT.md
    └── CUSTOMER_ONBOARDING.md
```

---

## 🔧 Technology Stack

### Core Framework
- **Language**: Python 3.10+
- **API Framework**: FastAPI 0.103+
- **ASGI Server**: Uvicorn

### Database & Caching
- **Database**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Cache**: Redis 7+

### AWS Integration
- **boto3**: 1.28+ - AWS SDK for Python
- **Spot Warnings**: EventBridge + SQS
- **EC2 Operations**: RunInstances, TerminateInstances, etc.

### Kubernetes Integration (Remote API)
- **kubernetes-client**: Official Python client
- **Authentication**: Service Account Token
- **NO AGENTS**: All operations via remote API calls

### Admin Frontend
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit
- **UI Library**: Material-UI (MUI)
- **Charts**: Recharts for cost visualization

### Monitoring
- **prometheus-client**: Metrics export
- **python-json-logger**: Structured logging

---

## 📦 Installation & Setup

### System Requirements

**Operating System**:
- Ubuntu 22.04 LTS or 24.04 LTS (recommended)
- Amazon Linux 2023
- Other Linux distributions (with adjustments)

**Hardware Minimum**:
- CPU: 4 cores (8 cores recommended for production)
- RAM: 16GB (32GB recommended for production)
- Disk: 100GB SSD (200GB+ for production with metrics)

**Software Prerequisites**:
- Python 3.10+ (3.11 recommended)
- PostgreSQL 15+
- Redis 7+
- Node.js 20.x LTS (for admin frontend)
- Docker (optional, for MySQL 8.0 compatibility from old setup)
- AWS CLI v2
- kubectl (for remote Kubernetes API access)

---

###Installation Script

**Automated Setup** (Ubuntu 22.04/24.04):

```bash
#!/bin/bash
# Core Platform Installation Script
# Based on old app/old-version/central-server/scripts/setup.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }

log "Starting Core Platform Installation..."

# Update system
log "Step 1: Updating system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install system dependencies
log "Step 2: Installing system dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    postgresql-15 postgresql-contrib \
    redis-server \
    nginx \
    curl wget git unzip jq \
    build-essential libpq-dev

# Install Docker (for MySQL 8.0 compatibility from old setup)
log "Step 3: Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

# Install Node.js 20.x LTS
log "Step 4: Installing Node.js 20.x LTS..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Install AWS CLI v2
log "Step 5: Installing AWS CLI v2..."
if ! command -v aws &> /dev/null; then
    cd /tmp
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install
    rm -rf aws awscliv2.zip
fi

# Install kubectl
log "Step 6: Installing kubectl..."
if ! command -v kubectl &> /dev/null; then
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl
fi

# Create directory structure
log "Step 7: Creating directory structure..."
APP_DIR="/opt/core-platform"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

mkdir -p $APP_DIR/api
mkdir -p $APP_DIR/services
mkdir -p $APP_DIR/database
mkdir -p $APP_DIR/admin-frontend
mkdir -p $APP_DIR/scripts
mkdir -p /var/log/core-platform

# Setup Python virtual environment
log "Step 8: Setting up Python environment..."
cd $APP_DIR/api
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
cat > requirements.txt << 'EOF'
# API Framework (from old app/old-version/central-server/backend/requirements.txt)
Flask==3.0.0
flask-cors==4.0.0
gunicorn==21.2.0

# Database
mysql-connector-python==8.2.0

# Scheduler
APScheduler==3.10.4

# Validation
marshmallow==3.20.1

# AWS
boto3==1.28.25
botocore==1.31.25

# Kubernetes (for remote API access)
kubernetes==27.2.0

# HTTP Client
requests==2.31.0
httpx==0.24.1

# Environment
python-dotenv==1.0.0

# Monitoring
prometheus-client==0.17.1
python-json-logger==2.0.7

# Testing
pytest==7.4.0
EOF

pip install --upgrade pip
pip install -r requirements.txt

log "Python dependencies installed"
deactivate

# Setup PostgreSQL database
log "Step 9: Configuring PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql << PSQL_EOF
CREATE DATABASE cloudoptim;
CREATE USER cloudoptim WITH ENCRYPTED PASSWORD 'cloudoptim_password';
GRANT ALL PRIVILEGES ON DATABASE cloudoptim TO cloudoptim;
\c cloudoptim
GRANT ALL ON SCHEMA public TO cloudoptim;
PSQL_EOF

log "PostgreSQL database created"

# Setup Redis
log "Step 10: Configuring Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Create environment configuration
log "Step 11: Creating environment configuration..."
cat > $APP_DIR/api/.env << 'ENV_EOF'
# Core Platform Configuration
CENTRAL_SERVER_HOST=0.0.0.0
CENTRAL_SERVER_PORT=8000
CENTRAL_SERVER_WORKERS=4

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cloudoptim
DB_USER=cloudoptim
DB_PASSWORD=cloudoptim_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# ML Server Connection
ML_SERVER_URL=http://ml-server:8001
ML_SERVER_API_KEY=change_this_api_key

# AWS
AWS_REGION=us-east-1

# EventBridge/SQS Polling
SQS_POLL_INTERVAL_SECONDS=5
SQS_MAX_MESSAGES=10

# Remote Kubernetes API
K8S_API_TIMEOUT_SECONDS=30
K8S_API_RETRY_ATTEMPTS=3

# Optimization
OPTIMIZATION_INTERVAL_MINUTES=10
BIN_PACKING_ENABLED=true
RIGHTSIZING_ENABLED=true
OFFICE_HOURS_ENABLED=true

# Feature Flags
GHOST_PROBE_SCANNER_ENABLED=true
ZOMBIE_VOLUME_CLEANUP_ENABLED=true
NETWORK_OPTIMIZATION_ENABLED=true
OOM_REMEDIATION_ENABLED=true
ENV_EOF

# Create systemd service
log "Step 12: Creating systemd service..."
sudo tee /etc/systemd/system/core-platform-backend.service > /dev/null << SERVICE_EOF
[Unit]
Description=Core Platform Backend (FastAPI)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR/api
EnvironmentFile=$APP_DIR/api/.env
ExecStart=$APP_DIR/api/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=append:/var/log/core-platform/backend.log
StandardError=append:/var/log/core-platform/backend-error.log

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl enable core-platform-backend

# Setup frontend
log "Step 13: Setting up admin frontend..."
cd $APP_DIR/admin-frontend
npm install
npm run build

# Configure Nginx
sudo tee /etc/nginx/sites-available/core-platform << 'NGINX_EOF'
server {
    listen 80 default_server;
    server_name _;

    root /opt/core-platform/admin-frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
NGINX_EOF

sudo ln -sf /etc/nginx/sites-available/core-platform /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Create helper scripts
log "Step 14: Creating helper scripts..."

cat > $APP_DIR/scripts/start.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "Starting Core Platform..."
sudo systemctl start core-platform-backend
sudo systemctl start nginx
echo "Core Platform started!"
SCRIPT_EOF
chmod +x $APP_DIR/scripts/start.sh

cat > $APP_DIR/scripts/status.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "=== Core Platform Status ==="
sudo systemctl status core-platform-backend --no-pager
echo ""
curl -s http://localhost:8000/health | jq .
SCRIPT_EOF
chmod +x $APP_DIR/scripts/status.sh

log "============================================"
log "Core Platform Installation Complete!"
log "============================================"
log ""
log "✓ Backend API: http://localhost:8000"
log "✓ Admin Frontend: http://localhost:80"
log "✓ Database: PostgreSQL (cloudoptim)"
log "✓ Cache: Redis"
log ""
log "Quick Commands:"
log "  Start: $APP_DIR/scripts/start.sh"
log "  Status: $APP_DIR/scripts/status.sh"
log "============================================"
```

**Save as**: `install_core_platform.sh`

**Run**:
```bash
chmod +x install_core_platform.sh
./install_core_platform.sh
```

---

### Version Reference (from old setup scripts)

**Python Packages**:
```txt
# API Framework
Flask==3.0.0
flask-cors==4.0.0
gunicorn==21.2.0

# Database
mysql-connector-python==8.2.0

# Scheduler
APScheduler==3.10.4

# AWS
boto3==1.28.25

# Kubernetes
kubernetes==27.2.0
```

**System Packages**:
- Python: 3.10+ (3.11 recommended)
- PostgreSQL: 15+ or MySQL 8.0 (via Docker)
- Redis: 7+
- Node.js: 20.x LTS
- Nginx: 1.18+
- kubectl: Latest stable
- Docker: 24.0+ (optional)

---

### Customer Onboarding Setup

For each customer cluster, configure these components:

#### 1. AWS Setup (Customer AWS Account)

```bash
# Create IAM role for CloudOptim
aws iam create-role --role-name CloudOptimRole \
  --assume-role-policy-document file://trust-policy.json

# Attach required permissions
aws iam attach-role-policy --role-name CloudOptimRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess

# Create SQS queue for Spot warnings
aws sqs create-queue --queue-name cloudoptim-spot-warnings

# Create EventBridge rule
aws events put-rule --name cloudoptim-spot-interruption \
  --event-pattern '{"source":["aws.ec2"],"detail-type":["EC2 Spot Instance Interruption Warning"]}'

# Connect EventBridge to SQS
aws events put-targets --rule cloudoptim-spot-interruption \
  --targets "Id"="1","Arn"="arn:aws:sqs:us-east-1:ACCOUNT:cloudoptim-spot-warnings"
```

#### 2. Kubernetes Setup (Customer Cluster)

```bash
# Create service account
kubectl create serviceaccount cloudoptim -n kube-system

# Apply RBAC (see RBAC section in memory)
kubectl apply -f cloudoptim-rbac.yaml

# Get service account token
kubectl create token cloudoptim -n kube-system --duration=87600h
```

#### 3. Register Customer in Core Platform

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/admin/clusters \
  -H "Content-Type: application/json" \
  -d '{
    "cluster_name": "production-eks",
    "k8s_api_endpoint": "https://EKS-ENDPOINT",
    "k8s_token": "SERVICE_ACCOUNT_TOKEN",
    "aws_role_arn": "arn:aws:iam::ACCOUNT:role/CloudOptimRole",
    "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/ACCOUNT/cloudoptim-spot-warnings",
    "region": "us-east-1"
  }'
```

---

### Verification

```bash
# Check services
sudo systemctl status core-platform-backend
sudo systemctl status postgresql
sudo systemctl status redis-server

# Test backend API
curl http://localhost:8000/health

# Test remote K8s API access (requires cluster registration)
curl http://localhost:8000/api/v1/k8s/CLUSTER_ID/nodes

# Test ML Server connectivity
curl http://ML_SERVER_URL/api/v1/ml/health
```

---

## 🚀 Deployment Configuration

### Environment Variables
```bash
# Server Configuration
CENTRAL_SERVER_HOST=0.0.0.0
CENTRAL_SERVER_PORT=8000
CENTRAL_SERVER_WORKERS=4

# Database
DB_HOST=postgres.internal
DB_PORT=5432
DB_NAME=cloudoptim
DB_USER=cloudoptim
DB_PASSWORD=xxx

# Redis Cache
REDIS_HOST=redis.internal
REDIS_PORT=6379

# ML Server Connection
ML_SERVER_URL=http://ml-server:8001
ML_SERVER_API_KEY=xxx

# AWS Configuration
AWS_REGION=us-east-1

# EventBridge/SQS Polling
SQS_POLL_INTERVAL_SECONDS=5
SQS_MAX_MESSAGES=10
SQS_VISIBILITY_TIMEOUT=30
SQS_WAIT_TIME_SECONDS=20  # Long polling

# Remote Kubernetes API
K8S_API_TIMEOUT_SECONDS=30
K8S_API_RETRY_ATTEMPTS=3
K8S_API_BACKOFF_FACTOR=2

# Optimization Settings
OPTIMIZATION_INTERVAL_MINUTES=10
BIN_PACKING_ENABLED=true
RIGHTSIZING_ENABLED=true
OFFICE_HOURS_ENABLED=true

# Feature Flags
GHOST_PROBE_SCANNER_ENABLED=true
ZOMBIE_VOLUME_CLEANUP_ENABLED=true
NETWORK_OPTIMIZATION_ENABLED=true
OOM_REMEDIATION_ENABLED=true
```

---

## 📊 Database Schema

### Core Tables

```sql
-- Customers
CREATE TABLE customers (
    customer_id UUID PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    aws_role_arn VARCHAR(512) NOT NULL,
    sqs_queue_url VARCHAR(512) NOT NULL,
    external_id VARCHAR(128) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Clusters
CREATE TABLE clusters (
    cluster_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(customer_id),
    cluster_name VARCHAR(255) NOT NULL,
    k8s_api_endpoint VARCHAR(512) NOT NULL,
    k8s_token TEXT NOT NULL,  -- Service account token (encrypted)
    region VARCHAR(50) NOT NULL,
    node_count INT NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Nodes
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters(cluster_id),
    node_name VARCHAR(255) NOT NULL,
    instance_id VARCHAR(50) NOT NULL,
    instance_type VARCHAR(50) NOT NULL,
    availability_zone VARCHAR(50) NOT NULL,
    node_type VARCHAR(20) NOT NULL,  -- spot, on-demand
    status VARCHAR(50) NOT NULL,
    cpu_cores DECIMAL(10,2),
    memory_gb DECIMAL(10,2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Spot Events
CREATE TABLE spot_events (
    event_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters(cluster_id),
    instance_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- interruption_warning, terminated
    event_time TIMESTAMP NOT NULL,
    received_at TIMESTAMP NOT NULL,
    action_taken VARCHAR(255),
    replacement_instance_id VARCHAR(50),
    drain_duration_seconds INT,
    processed_at TIMESTAMP
);

-- Optimization History
CREATE TABLE optimization_history (
    optimization_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters(cluster_id),
    optimization_type VARCHAR(50) NOT NULL,  -- spot_optimize, bin_pack, rightsize
    recommendations JSONB NOT NULL,
    execution_plan JSONB NOT NULL,
    estimated_savings DECIMAL(10,2),
    actual_savings DECIMAL(10,2),
    status VARCHAR(50) NOT NULL,
    executed_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);

-- Customer Config
CREATE TABLE customer_config (
    config_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(customer_id),
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(customer_id, config_key)
);

-- Metrics Summary
CREATE TABLE metrics_summary (
    metric_id BIGSERIAL PRIMARY KEY,
    cluster_id UUID REFERENCES clusters(cluster_id),
    metric_type VARCHAR(50) NOT NULL,  -- cpu, memory, cost
    value DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMP NOT NULL
);

-- Ghost Instances (zombie EC2 instances not in K8s)
CREATE TABLE ghost_instances (
    ghost_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers(customer_id),
    instance_id VARCHAR(50) NOT NULL,
    instance_type VARCHAR(50),
    region VARCHAR(50),
    detected_at TIMESTAMP NOT NULL,
    terminated_at TIMESTAMP,
    status VARCHAR(50) NOT NULL  -- detected, flagged, terminated
);
```

---

## 📝 API Specifications

### Customer & Cluster Management
```http
GET  /api/v1/admin/clusters         - List all clusters
POST /api/v1/admin/clusters         - Register new cluster
GET  /api/v1/admin/clusters/{id}    - Get cluster details
PUT  /api/v1/admin/clusters/{id}    - Update cluster config
DELETE /api/v1/admin/clusters/{id}  - Remove cluster
GET  /api/v1/admin/savings          - Get real-time savings
```

### Optimization Endpoints
```http
POST /api/v1/optimization/trigger   - Trigger optimization for cluster
GET  /api/v1/optimization/history   - Get optimization history
GET  /api/v1/optimization/status/{id} - Get optimization status
```

### EventBridge Integration
```http
GET  /api/v1/events/spot-warnings   - Get recent Spot warnings
POST /api/v1/events/process         - Manually process Spot event
GET  /api/v1/events/history         - Get event processing history
```

### Remote Kubernetes Operations (Agentless)
```http
GET  /api/v1/k8s/{cluster_id}/nodes         - List cluster nodes
GET  /api/v1/k8s/{cluster_id}/pods          - List cluster pods
GET  /api/v1/k8s/{cluster_id}/metrics       - Get cluster metrics
POST /api/v1/k8s/{cluster_id}/nodes/drain   - Drain node remotely
POST /api/v1/k8s/{cluster_id}/nodes/cordon  - Cordon node remotely
POST /api/v1/k8s/{cluster_id}/scale         - Scale deployment
```

### Ghost Probe Scanner
```http
POST /api/v1/scanner/scan           - Scan for ghost instances
GET  /api/v1/scanner/ghosts         - List detected ghost instances
POST /api/v1/scanner/terminate/{id} - Terminate ghost instance
```

---

## 🔄 Key Workflows (Agentless)

### Workflow 1: Spot Interruption Handling
```
1. AWS EventBridge detects Spot interruption (2-minute warning)
2. EventBridge sends event to customer SQS queue
3. Core Platform polls SQS queue (every 5 seconds)
4. Core Platform receives interruption warning
5. Core Platform calls remote K8s API to drain node
6. Core Platform launches replacement instance via EC2 API
7. New node joins cluster (kubelet self-registers)
8. Workloads rescheduled to new node
9. Core Platform terminates old instance after drain completes
```

### Workflow 2: Spot Optimization
```
1. Core Platform polls cluster metrics via remote K8s API
2. Core Platform sends cluster state to ML Server
3. ML Server analyzes and returns Spot recommendations
4. Core Platform validates recommendations
5. Core Platform launches new Spot instances via EC2 API
6. Core Platform drains old instances via remote K8s API
7. Core Platform monitors migration progress
8. Core Platform updates database with savings
```

### Workflow 3: Bin Packing
```
1. Core Platform fetches pod scheduling data via remote K8s API
2. Core Platform sends data to ML Server
3. ML Server returns consolidation plan
4. Core Platform cordons underutilized nodes via remote K8s API
5. Core Platform drains cordoned nodes via remote K8s API
6. Pods reschedule to remaining nodes
7. Core Platform terminates empty nodes via EC2 API
8. Cluster now consolidated with fewer nodes
```

### Workflow 4: Ghost Probe Scanner
```
1. Core Platform scans customer AWS account (DescribeInstances)
2. Core Platform fetches K8s nodes via remote K8s API
3. Core Platform compares EC2 instances vs K8s nodes
4. Identifies ghost instances (EC2 running but not in K8s)
5. Flags ghost instances in database
6. After 24-hour grace period, terminates ghost instances
7. Notifies customer via webhook
```

---

## 🧪 Testing

### Unit Tests
```bash
pytest tests/test_api.py
pytest tests/test_services.py
pytest tests/test_k8s_client.py
pytest tests/test_eventbridge.py
```

### Integration Tests
```bash
pytest tests/integration/test_spot_handling.py
pytest tests/integration/test_k8s_remote_api.py
pytest tests/integration/test_ml_integration.py
```

---

## 🐛 Troubleshooting

### Remote K8s API Connection Fails
**Symptom**: "Unable to connect to Kubernetes API"
**Solution**: Check service account token, verify RBAC permissions, check network access

### SQS Polling Not Receiving Events
**Symptom**: Spot warnings not processed
**Solution**: Verify EventBridge rule, check SQS queue permissions, verify IAM role

### High API Response Latency
**Symptom**: API response time > 2 seconds
**Solution**: Enable Redis caching, increase workers, check DB connection pool

---

## 📌 Important Notes

1. **Agentless Architecture**: NO DaemonSets or client-side agents
2. **Remote K8s API**: All operations via remote HTTPS calls
3. **EventBridge + SQS**: For Spot interruption warnings
4. **Public Data First**: Day Zero operation using AWS Spot Advisor
5. **Service Account Token**: Customer provides, encrypted at rest

---

## 🎯 Integration Checklist

- [ ] PostgreSQL database setup
- [ ] ML Server API endpoint configured
- [ ] Remote Kubernetes API client tested
- [ ] EventBridge/SQS polling service running
- [ ] AWS IAM role configured (cross-account)
- [ ] Admin frontend deployed
- [ ] Redis cache connection tested
- [ ] Health check endpoints responding
- [ ] Logging forwarding configured

---

**END OF SESSION MEMORY - CORE PLATFORM (AGENTLESS ARCHITECTURE)**
