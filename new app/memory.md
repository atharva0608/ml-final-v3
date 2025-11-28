# CloudOptim – Agentless Kubernetes Cost Optimization (CAST AI Competitor)

**Last Updated**: 2025-11-28
**Status**: Architecture Defined - Ready for Implementation
**Architecture**: Agentless (EventBridge + SQS + Remote Kubernetes API)

---

## 🎯 High-Level Goal

Build a **CAST AI competitor** that:
- ❌ **NO AGENTS** - No DaemonSets, no client-side components
- ✅ **Remote Kubernetes API** - Direct API calls to customer clusters
- ✅ **AWS EventBridge + SQS** - For Spot interruption warnings (2-minute notices)
- ✅ **Public Spot Advisor Data** - No customer data needed for Day Zero
- ✅ **Inference-Only ML Server** - Upload pre-trained models, no training on production

---

## 🏗️ Two-Server Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  Customer AWS Account                          │
│                                                                 │
│  ┌──────────────────┐        ┌────────────────────┐          │
│  │   EKS Cluster    │        │  EventBridge Rule  │          │
│  │                  │        │  + SQS Queue       │          │
│  │  (No agent!)     │        │                    │          │
│  │                  │        │  Spot interruption │          │
│  │  Workloads       │        │  warnings          │          │
│  └──────────────────┘        └────────┬───────────┘          │
│         ▲                              │                      │
│         │ K8s API (remote)             │ SQS polling         │
│         │                              │                      │
└─────────┼──────────────────────────────┼──────────────────────┘
          │                              │
          │                              │
    ┌─────┴──────────────────────────────┴─────┐
    │                                           │
    │  CloudOptim Control Plane                │
    │                                           │
    │  ┌─────────────────────────────────────┐ │
    │  │     Core Platform                   │ │
    │  │  • Central Backend (FastAPI)        │ │
    │  │  • PostgreSQL Database              │ │
    │  │  • Admin Frontend (React)           │ │
    │  │  • EventBridge/SQS Polling          │ │
    │  │  • Remote K8s API Client            │ │
    │  │  • AWS EC2 API Client               │ │
    │  └──────────────┬──────────────────────┘ │
    │                 │ REST API                │
    │  ┌──────────────┴──────────────────────┐ │
    │  │     ML Server                       │ │
    │  │  • Model Hosting (inference-only)  │ │
    │  │  • Decision Engines (pluggable)    │ │
    │  │  • Data Gap Filler                 │ │
    │  │  • Spot Advisor Data Cache         │ │
    │  └─────────────────────────────────────┘ │
    │                                           │
    └───────────────────────────────────────────┘
```

---

## 🚀 Key Features (CAST AI Parity)

### 1. Spot Instance Arbitrage with Fallback
**How It Works**:
- Uses **AWS Spot Advisor** public data (no customer data needed)
- Risk scoring formula:
  ```
  Risk Score = (0.60 × Public_Rate) +
               (0.25 × Volatility) +
               (0.10 × Gap_Score) +
               (0.05 × Time_Score)
  ```
- Automatic fallback to on-demand on interruption
- Receives 2-minute warnings via **EventBridge → SQS**

**Data Source**: `https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json`

### 2. Bin Packing (Tetris Engine)
**How It Works**:
- Consolidates workloads to minimize node count
- Rebalances cluster to free up underutilized nodes
- Terminates empty nodes automatically
- Defragmentation runs every 10 minutes

**Day Zero**: Works immediately using Kubernetes Metrics API (remote)

### 3. Rightsizing
**Node-Level**:
- Replaces oversized nodes with smaller instances
- Monitors CPU/memory utilization via remote Metrics API
- Deterministic lookup tables (no ML needed for Day Zero)

**Workload-Level**:
- Suggests CPU/memory request adjustments for deployments
- Uses 95th percentile of actual usage over 7 days

### 4. Office Hours Scheduler
**How It Works**:
- Auto-scale dev/staging clusters to zero during off-hours
- Schedule: 9 AM - 6 PM weekdays, scale down after hours
- Scale back up before business hours
- Saves ~65% on non-production environments

### 5. Zombie Volume Cleanup
**How It Works**:
- Detects EBS volumes not attached to any instance
- Checks if PVC still exists in Kubernetes
- Deletes orphaned volumes after 7-day grace period
- Typical savings: 5-10% of storage costs

### 6. Network Traffic Optimization
**How It Works**:
- Analyzes cross-AZ traffic patterns
- Places pods with affinity rules to minimize cross-AZ traffic
- Saves on AWS data transfer costs (cross-AZ = $0.01/GB)

### 7. OOMKilled Auto-Remediation
**How It Works**:
- Detects pods killed due to out-of-memory
- Automatically increases memory requests by 20%
- Redeploys pod with updated resource requests
- Prevents future OOM crashes

### 8. Ghost Probe Scanner
**How It Works**:
- Scans AWS account for running EC2 instances **not in Kubernetes**
- Identifies "ghost" instances (zombie instances left behind)
- Flags for manual review or auto-terminates after 24 hours
- Day Zero compatible: no historical data needed

---

## 🔧 Agentless Architecture Details

### Remote Kubernetes API Access
**No DaemonSets Needed**:
- Customer provides kubeconfig (service account token)
- CloudOptim makes **remote API calls** to K8s API server:
  ```
  GET /api/v1/nodes
  GET /api/v1/pods
  GET /apis/metrics.k8s.io/v1beta1/nodes
  POST /api/v1/namespaces/{ns}/pods/{pod}/eviction
  PATCH /api/v1/nodes/{name}
  ```

**RBAC Permissions Required**:
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
```

### AWS EventBridge + SQS Integration
**Spot Interruption Warnings**:
1. Customer creates EventBridge rule in their AWS account:
   ```json
   {
     "source": ["aws.ec2"],
     "detail-type": ["EC2 Spot Instance Interruption Warning"],
     "detail": {
       "instance-id": [{"prefix": ""}]
     }
   }
   ```
2. Rule sends events to SQS queue
3. CloudOptim polls SQS queue every 5 seconds
4. Receives 2-minute warning before Spot termination
5. Drains node and launches replacement immediately

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

### AWS API Integration (EC2)
**No Customer Data Needed**:
- Launch/terminate instances via EC2 API
- Query Spot prices: `DescribeSpotPriceHistory`
- Get Spot placement scores: `GetSpotPlacementScores`
- All done remotely, no agents

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
        "ec2:GetSpotPlacementScores",
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

---

## 📁 Repository Structure

```
new app/
├── memory.md                   # This file
├── ml-server/                  # ML inference & decision engine server
│   ├── SESSION_MEMORY.md      # ML server documentation
│   ├── models/                 # Model hosting (uploaded models)
│   ├── decision_engine/        # Pluggable decision engines
│   ├── data/                   # Gap filler & data fetchers
│   ├── api/                    # FastAPI server
│   └── ...
├── core-platform/              # Central backend, DB, admin UI
│   ├── SESSION_MEMORY.md      # Core platform documentation
│   ├── api/                    # Main REST API
│   ├── database/               # PostgreSQL schema & migrations
│   ├── admin-frontend/         # React admin dashboard
│   ├── services/               # Business logic
│   │   ├── eventbridge_poller.py   # SQS poller for Spot warnings
│   │   ├── k8s_remote_client.py    # Remote K8s API client
│   │   └── spot_handler.py         # Spot interruption handler
│   └── ...
├── common/                     # Shared components
│   ├── INTEGRATION_GUIDE.md   # Integration documentation
│   ├── schemas/                # Pydantic models
│   ├── auth/                   # Authentication
│   └── config/                 # Common configuration
└── infra/                      # Infrastructure as Code
    ├── docker-compose.yml      # Local development
    ├── kubernetes/             # K8s manifests
    └── terraform/              # Cloud infrastructure
```

---

## 🔗 API Endpoints

### ML Server (Port 8001)
```http
# Model Management
POST /api/v1/ml/models/upload       - Upload pre-trained model
GET  /api/v1/ml/models/list         - List models
POST /api/v1/ml/models/activate     - Activate model version

# Decision Engines
POST /api/v1/ml/engines/upload      - Upload decision engine
GET  /api/v1/ml/engines/list        - List engines
POST /api/v1/ml/engines/select      - Select active engine

# Gap Filling
POST /api/v1/ml/gap-filler/analyze  - Analyze data gaps
POST /api/v1/ml/gap-filler/fill     - Fill gaps with AWS data

# Predictions & Decisions
POST /api/v1/ml/predict/spot-interruption  - Predict interruption
POST /api/v1/ml/decision/spot-optimize     - Spot optimization
POST /api/v1/ml/decision/bin-pack          - Bin packing
POST /api/v1/ml/decision/rightsize         - Rightsizing
```

### Core Platform (Port 8000)
```http
# Customer & Cluster Management
GET  /api/v1/admin/clusters         - List clusters
POST /api/v1/admin/clusters         - Register new cluster
GET  /api/v1/admin/savings          - Real-time savings

# Optimization
POST /api/v1/optimization/trigger   - Trigger optimization
GET  /api/v1/optimization/history   - Optimization history

# EventBridge Integration
GET  /api/v1/events/spot-warnings   - Recent Spot warnings
POST /api/v1/events/process         - Process Spot event manually

# Remote Kubernetes Operations
GET  /api/v1/k8s/{cluster_id}/nodes         - Get cluster nodes
POST /api/v1/k8s/{cluster_id}/nodes/drain   - Drain node
POST /api/v1/k8s/{cluster_id}/nodes/cordon  - Cordon node
```

---

## 📊 Day Zero Operation (No Customer Data)

CloudOptim works **immediately** without historical data:

### 1. Spot Advisor Data (Public)
- Download from AWS: `spot-advisor-data.json`
- Contains interruption rates for all instance types
- Updated by AWS, publicly available
- **No customer data needed**

### 2. Ghost Probe Scanner
- Scans customer AWS account for EC2 instances
- Cross-references with Kubernetes nodes
- Identifies zombie instances immediately
- **No historical data needed**

### 3. Rightsizing (Deterministic)
- Uses lookup tables for common workload patterns
- Reads current metrics from Kubernetes Metrics API
- Makes recommendations based on current state
- **No historical data needed**

### 4. Bin Packing
- Uses current pod scheduling data from K8s API
- Simulates rebalancing scenarios
- Finds optimal consolidation immediately
- **No historical data needed**

---

## 🔄 Inference-Only ML Server

### Model Upload Flow
1. User uploads pre-trained model (`.pkl` file) via admin UI
2. ML server stores model in `/models/uploaded/{model_id}.pkl`
3. Extracts metadata (trained_until date)
4. User triggers gap-fill if needed
5. ML server activates model for predictions

### Gap-Filling Process
**Problem**: Model trained on October data, need predictions for November
**Solution**:
1. ML server detects gap (trained_until → today)
2. Automatically fetches historic Spot prices from AWS API
3. Fills feature engineering pipeline with historic data
4. Model ready for up-to-date predictions immediately

### Decision Engine (Pluggable)
- Upload Python modules via frontend
- Fixed input format (metrics, prices, states)
- Fixed output format (actions, scores, explanations)
- Hot-swap engines without downtime
- A/B test different decision strategies

---

## 📝 Configuration

### Core Platform Environment Variables
```bash
# Server
CENTRAL_SERVER_HOST=0.0.0.0
CENTRAL_SERVER_PORT=8000

# Database
DB_HOST=postgres.internal
DB_PORT=5432
DB_NAME=cloudoptim
DB_USER=cloudoptim
DB_PASSWORD=xxx

# Redis
REDIS_HOST=redis.internal
REDIS_PORT=6379

# ML Server
ML_SERVER_URL=http://ml-server:8001
ML_SERVER_API_KEY=xxx

# AWS
AWS_REGION=us-east-1

# EventBridge/SQS Polling
SQS_POLL_INTERVAL_SECONDS=5
SQS_MAX_MESSAGES=10
SQS_VISIBILITY_TIMEOUT=30

# Kubernetes Remote API
K8S_API_TIMEOUT_SECONDS=30
K8S_API_RETRY_ATTEMPTS=3
```

### ML Server Environment Variables
```bash
# Server
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001

# Models
MODEL_UPLOAD_DIR=/app/models/uploaded
ALLOW_MODEL_TRAINING=false  # Explicitly disabled

# Gap Filler
GAP_FILLER_ENABLED=true
GAP_FILLER_AWS_REGION=us-east-1
GAP_FILLER_HISTORIC_DAYS_MAX=90

# Decision Engines
DECISION_ENGINE_DIR=/app/engines
DECISION_ENGINE_ACTIVE=spot_optimizer_v1

# Storage
REDIS_HOST=redis.internal
REDIS_PORT=6379

# Central Platform
CENTRAL_PLATFORM_URL=http://core-platform:8000
CENTRAL_PLATFORM_API_KEY=xxx
```

---

## 🎯 Implementation Roadmap

### Phase 1: Core Infrastructure
- [ ] Setup PostgreSQL database schema
- [ ] Create FastAPI server for core platform
- [ ] Implement remote Kubernetes API client
- [ ] Setup EventBridge/SQS polling service

### Phase 2: ML Server
- [ ] Create ML server with FastAPI
- [ ] Implement model upload endpoints
- [ ] Create data gap filler with AWS integration
- [ ] Implement decision engine registry

### Phase 3: Features
- [ ] Spot arbitrage with risk scoring
- [ ] Bin packing engine
- [ ] Rightsizing engine
- [ ] Office hours scheduler
- [ ] Zombie volume cleanup
- [ ] Network optimization
- [ ] OOMKilled remediation
- [ ] Ghost probe scanner

### Phase 4: Admin Frontend
- [ ] Create React admin dashboard
- [ ] Model upload UI
- [ ] Live cost monitoring
- [ ] Prediction vs actual charts
- [ ] Cluster management UI
- [ ] Optimization history

### Phase 5: Testing & Production
- [ ] Integration testing
- [ ] Load testing
- [ ] Security audit
- [ ] Production deployment
- [ ] Documentation

---

## 🔐 Security Considerations

### Customer Onboarding
1. Customer creates IAM role with CloudOptim trust policy
2. Customer creates EventBridge rule + SQS queue
3. Customer creates Kubernetes service account + RBAC
4. Customer provides:
   - AWS IAM Role ARN
   - SQS Queue URL
   - Kubernetes API endpoint
   - Kubernetes service account token

### Data Security
- All communication over HTTPS/TLS
- No customer data leaves their account
- CloudOptim only makes API calls, doesn't store workload data
- Service account tokens encrypted at rest
- IAM roles follow least-privilege principle

---

**Last Updated**: 2025-11-28
**Status**: Ready for implementation
**Architecture**: Agentless (No DaemonSets, remote API only)
