# Core Platform - CloudOptim

**Central Control Plane for Agentless Kubernetes Cost Optimization**

## Overview

Core Platform is the main control plane that:
- **Monitors** customer Kubernetes clusters via remote API (NO agents)
- **Coordinates** with ML Server for optimization decisions
- **Executes** optimization plans remotely (via K8s API + AWS APIs)
- **Handles** Spot interruptions via EventBridge/SQS
- **Provides** admin dashboard for monitoring and management

## Architecture

**Agentless Design**:
- ❌ NO DaemonSets or client-side agents
- ✅ Remote Kubernetes API calls only
- ✅ AWS EventBridge + SQS for Spot warnings
- ✅ ML Server for ALL decision-making
- ✅ Core Platform executes decisions only

**Components**:
- **Backend**: FastAPI (Port 8000)
- **Admin Frontend**: React + TypeScript (Port 80)
- **Database**: PostgreSQL (cluster data, metrics, history)
- **Cache**: Redis (cluster state, metrics)

## Quick Start

### Prerequisites
- Python 3.10+ (3.11 recommended)
- PostgreSQL 15+
- Redis 7+
- Node.js 20.x LTS
- kubectl (for remote K8s API access)
- AWS CLI v2

### Installation

```bash
# Automated installation (Ubuntu 22.04/24.04)
./scripts/install.sh

# Or manual installation
pip install -r requirements.txt
npm install --prefix admin-frontend
```

### Configuration

Edit `api/.env`:
```bash
CENTRAL_SERVER_HOST=0.0.0.0
CENTRAL_SERVER_PORT=8000
DB_HOST=localhost
DB_NAME=cloudoptim
REDIS_HOST=localhost
ML_SERVER_URL=http://localhost:8001
```

### Start Services

```bash
# Backend
./scripts/start_backend.sh

# Frontend
./scripts/start_frontend.sh
```

### Access

- **Backend API**: http://localhost:8000/api/v1/
- **API Docs**: http://localhost:8000/api/v1/docs
- **Admin Dashboard**: http://localhost:80
- **Health Check**: http://localhost:8000/health

## Features

### 1. Remote Cluster Management (Agentless)
- List nodes/pods via remote K8s API
- Get metrics via Metrics Server API  
- Drain/cordon nodes remotely
- Scale deployments remotely
- **NO agents or DaemonSets required**

### 2. Spot Interruption Handling
- Poll SQS queues (every 5 seconds)
- Receive 2-minute warnings from EventBridge
- Drain node automatically
- Launch replacement instance
- Complete process within 2 minutes

### 3. Optimization Orchestration
- Collect cluster state remotely
- Send to ML Server for decisions
- Receive optimization recommendations
- Execute plans via remote APIs
- Track results in database

### 4. Admin Dashboard (Enhanced UX)
- Real-time cost monitoring
- Predictions vs actual comparison
- Cluster management interface
- Optimization history viewer
- Live Spot warning feed
- Interactive charts (Recharts)
- Dark theme for better visibility

### 5. Ghost Probe Scanner
- Scan AWS account for EC2 instances
- Compare with K8s nodes
- Identify zombie instances
- Terminate after 24-hour grace period

### 6. Data Collection for ML Server
- EC2 instance lists
- EBS volume lists
- Pod event logs (OOMKilled)
- Network traffic metrics
- Sends to ML Server for analysis

## API Endpoints

### Clusters
```http
GET  /api/v1/admin/clusters         # List all clusters
POST /api/v1/admin/clusters         # Register new cluster
GET  /api/v1/admin/clusters/{id}    # Get cluster details
GET  /api/v1/admin/savings          # Get real-time savings
```

### Optimization
```http
POST /api/v1/optimization/trigger   # Trigger optimization
GET  /api/v1/optimization/history   # Get optimization history
GET  /api/v1/optimization/status/{id} # Get status
```

### Events (Spot Warnings)
```http
GET  /api/v1/events/spot-warnings   # Recent Spot warnings
GET  /api/v1/events/history         # Event processing history
```

### Remote K8s Operations
```http
GET  /api/v1/k8s/{cluster_id}/nodes         # List nodes
GET  /api/v1/k8s/{cluster_id}/pods          # List pods
POST /api/v1/k8s/{cluster_id}/nodes/drain   # Drain node
POST /api/v1/k8s/{cluster_id}/scale         # Scale deployment
```

See `docs/API_SPEC.md` and `SESSION_MEMORY.md` for complete API documentation.

## Database Schema

PostgreSQL tables:
- `customers` - Customer accounts
- `clusters` - Registered Kubernetes clusters
- `nodes` - Cluster nodes
- `spot_events` - Spot interruption events
- `optimization_history` - Optimization execution history
- `customer_config` - Customer configuration
- `metrics_summary` - Aggregated metrics
- `ghost_instances` - Detected zombie instances

See `SESSION_MEMORY.md` lines 905-1011 for complete schema.

## Customer Onboarding

### 1. AWS Setup (Customer Account)
```bash
# Create IAM role
aws iam create-role --role-name CloudOptimRole \
  --assume-role-policy-document file://trust-policy.json

# Create SQS queue
aws sqs create-queue --queue-name cloudoptim-spot-warnings

# Create EventBridge rule
aws events put-rule --name cloudoptim-spot-interruption \
  --event-pattern '{"source":["aws.ec2"],"detail-type":["EC2 Spot Instance Interruption Warning"]}'
```

### 2. Kubernetes Setup (Customer Cluster)
```bash
# Create service account
kubectl create serviceaccount cloudoptim -n kube-system

# Apply RBAC
kubectl apply -f cloudoptim-rbac.yaml

# Get token
kubectl create token cloudoptim -n kube-system --duration=87600h
```

### 3. Register in Core Platform
```bash
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

## Development

### Run Tests
```bash
pytest tests/
```

### Database Migrations
```bash
cd api
alembic upgrade head
```

## Production Deployment

### Docker Compose
```bash
docker-compose up -d
```

### Systemd Service
```bash
sudo systemctl start core-platform-backend
sudo systemctl status core-platform-backend
```

## Security

- Service account tokens encrypted at rest
- All remote K8s API calls over HTTPS
- IAM roles with least-privilege permissions
- SQS queue access restricted to Core Platform
- API key authentication for ML Server communication

## Documentation

- **SESSION_MEMORY.md**: Complete implementation guide (1172 lines)
- **docs/API_SPEC.md**: API endpoint reference
- **docs/DEPLOYMENT.md**: Production deployment guide
- **docs/CUSTOMER_ONBOARDING.md**: Onboarding instructions

## Integration with ML Server

Core Platform acts as the "executor", ML Server as the "brain":

```
Core Platform → ML Server: "Here's cluster state, what should I do?"
ML Server → Core Platform: "Here are recommendations with execution plan"
Core Platform → Customer Cluster: Executes plan via remote K8s API + AWS APIs
```

Core Platform **never** makes optimization decisions - only executes them.

## License

Proprietary - CloudOptim

## Support

For issues and questions, refer to SESSION_MEMORY.md or contact the development team.

---

**Last Updated**: 2025-11-28
**Version**: 1.0.0
**Architecture**: Agentless (No DaemonSets, remote API only)
