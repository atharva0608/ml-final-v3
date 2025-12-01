# CloudOptim - Agentless Kubernetes Cost Optimization (CAST AI Competitor)

**Version**: 2.0
**Created**: 2025-11-28
**Updated**: 2025-11-29
**Architecture**: Agentless (Remote K8s API + EventBridge + SQS)

---

## 📋 Overview

CloudOptim is an **agentless Kubernetes cost optimization platform** (CAST AI competitor) with the following architecture:

1. **ML Server**: Inference-only with 8 CAST AI decision engines (Spot optimization, bin packing, rightsizing, etc.)
2. **Core Platform**: Agentless executor using Remote K8s API (NO DaemonSets, NO client-side agents)
3. **EventBridge + SQS**: AWS Spot interruption warnings (2-minute notice)
4. **Day Zero Operation**: Works immediately with public AWS Spot Advisor data
5. **Automatic Gap-Filling**: Solves "trained until October, need data until today" problem

---

## 🗂️ Folder Structure

```
new app/
├── README.md                   # This file
├── memory.md                   # Architecture memory & documentation
├── ml-server/                  # ML inference & decision engine server
│   ├── SESSION_MEMORY.md      # ML server documentation
│   ├── backend/                # FastAPI backend
│   ├── models/                 # Model hosting (uploaded models)
│   ├── decision_engine/        # 8 CAST AI decision engines
│   ├── ml-frontend/            # React ML management frontend
│   └── ...
├── core-platform/              # Agentless executor platform
│   ├── SESSION_MEMORY.md      # Core platform documentation
│   ├── api/                    # Main REST API
│   ├── database/               # PostgreSQL schema
│   ├── services/               # Agentless services (K8s remote client, SQS poller, Spot handler)
│   ├── admin-frontend/         # React admin dashboard (enhanced UX)
│   └── ...
├── common/                     # Shared components
│   ├── INTEGRATION_GUIDE.md   # Integration documentation
│   ├── CHANGES.md              # Cross-component changes log
│   ├── schemas/                # Shared Pydantic models
│   ├── auth/                   # Authentication utilities
│   └── config/                 # Common configuration
└── infra/                      # Infrastructure as Code
    ├── docker-compose.yml      # Local development
    ├── kubernetes/             # K8s manifests
    └── README.md               # Infrastructure documentation
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Node.js 20+ (for frontends)

### Local Development with Docker Compose

```bash
# Start all services
cd infra/
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f ml-server
docker-compose logs -f core-platform
```

**Service URLs**:
- **Core Platform API**: http://localhost:8000
- **ML Server API**: http://localhost:8001
- **Admin Frontend**: http://localhost:3000
- **ML Frontend**: http://localhost:3001

---

## 📖 Documentation

### Component Documentation
Each component has detailed `SESSION_MEMORY.md`:
- **[ml-server/SESSION_MEMORY.md](./ml-server/SESSION_MEMORY.md)** - ML server architecture & 8 decision engines
- **[core-platform/SESSION_MEMORY.md](./core-platform/SESSION_MEMORY.md)** - Agentless executor architecture

### Architecture Documentation
- **[memory.md](./memory.md)** - Complete agentless architecture overview
- **[common/INTEGRATION_GUIDE.md](./common/INTEGRATION_GUIDE.md)** - Integration patterns
- **[common/CHANGES.md](./common/CHANGES.md)** - Cross-component changes log
- **[infra/README.md](./infra/README.md)** - Infrastructure documentation

---

## 🎯 Key Features (CAST AI Parity)

### 1. Spot Instance Optimization
- Uses **AWS Spot Advisor** public data (Day Zero ready)
- Risk scoring algorithm with 4 factors
- Automatic fallback to On-Demand
- 2-minute warning via EventBridge + SQS

### 2. Bin Packing (Tetris)
- Consolidates workloads to minimize nodes
- Automatic node termination when empty
- Runs every 10 minutes

### 3. Rightsizing
- Node-level and workload-level
- CPU/memory optimization
- Deterministic lookup tables (Day Zero ready)

### 4. Office Hours Scheduler
- Auto-scale dev/staging to zero after hours
- Schedule: 9 AM - 6 PM weekdays
- ~65% savings on non-production

### 5. Ghost Probe Scanner
- Detects zombie EC2 instances
- Flags instances not in Kubernetes
- Auto-terminate after 24-hour grace period

### 6. Zombie Volume Cleanup
- Finds unattached EBS volumes
- 7-day grace period before deletion
- 5-10% storage cost savings

### 7. Network Optimizer
- Cross-AZ traffic affinity optimization
- Reduces AWS data transfer costs

### 8. OOMKilled Remediation
- Auto-detects OOMKilled pods
- Increases memory by 20%
- Redeploys with updated limits

---

## 🔗 API Endpoints

### ML Server (Port 8001)
```
POST /api/v1/ml/models/upload         - Upload pre-trained model
POST /api/v1/ml/decision/spot-optimize - Spot instance optimization
POST /api/v1/ml/decision/bin-pack     - Bin packing decision
POST /api/v1/ml/decision/rightsize    - Rightsizing recommendation
POST /api/v1/ml/decision/schedule     - Office hours scheduling
POST /api/v1/ml/decision/ghost-probe  - Ghost instance detection
POST /api/v1/ml/decision/volume-cleanup - Zombie volume cleanup
POST /api/v1/ml/decision/network-optimize - Network optimization
POST /api/v1/ml/decision/oomkilled-remediate - OOMKilled auto-fix
POST /api/v1/ml/gap-filler/fill       - Fill data gaps
```

### Core Platform (Port 8000)
```
GET  /api/v1/admin/clusters           - List clusters
GET  /api/v1/admin/savings            - Real-time savings
POST /api/v1/optimization/trigger     - Trigger optimization
POST /api/v1/customer/onboard         - Customer onboarding
GET  /api/v1/ml/health                - ML Server health check
```

---

## 📊 Agentless Architecture

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
│  └────────▲─────────┘        └────────┬───────────┘          │
│           │ K8s API (remote)          │ SQS polling           │
│           │ HTTPS                     │                       │
└───────────┼───────────────────────────┼───────────────────────┘
            │                           │
            │                           │
    ┌───────┴───────────────────────────┴───────┐
    │                                            │
    │  CloudOptim Control Plane                 │
    │                                            │
    │  ┌──────────────────────────────────────┐ │
    │  │     Core Platform (Port 8000)       │ │
    │  │  • Remote K8s API Client            │ │
    │  │  • EventBridge/SQS Poller           │ │
    │  │  • AWS EC2 API Client               │ │
    │  │  • Admin Frontend (React)           │ │
    │  │  • PostgreSQL Database              │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │ REST API                 │
    │  ┌──────────────┴───────────────────────┐ │
    │  │     ML Server (Port 8001)            │ │
    │  │  • 8 CAST AI Decision Engines       │ │
    │  │  • Model Hosting (inference-only)   │ │
    │  │  • Data Gap Filler                  │ │
    │  │  • Redis Cache (Spot Advisor)       │ │
    │  │  • ML Frontend (React)              │ │
    │  └──────────────────────────────────────┘ │
    │                                            │
    └────────────────────────────────────────────┘
```

**Key Points**:
- ❌ NO DaemonSets in customer clusters
- ❌ NO client-side agents
- ✅ Remote Kubernetes API access only
- ✅ AWS EventBridge + SQS for Spot warnings
- ✅ AWS EC2 API for instance management

---

## 🧪 Testing

```bash
# ML Server tests
cd ml-server && pytest tests/

# Core Platform tests
cd core-platform && pytest tests/

# Integration tests (ML Server ↔ Core Platform)
pytest integration_tests/
```

---

## 🚢 Deployment

### Docker Compose (Development)
```bash
cd infra/
docker-compose up -d
```

### Kubernetes (Production)
```bash
cd infra/kubernetes/

# Create namespace
kubectl create namespace cloudoptim

# Create secrets
kubectl create secret generic ml-server-secrets \
  --from-literal=database-url="..." \
  --from-literal=redis-url="..." \
  -n cloudoptim

# Deploy ML Server
kubectl apply -f ml-server/deployment.yaml

# Deploy Core Platform
kubectl apply -f core-platform/deployment.yaml

# Note: NO client agent needed (agentless!)
```

---

## 🔄 Development Workflow

1. **Read the session memory**: `{component}/SESSION_MEMORY.md`
2. **Make changes** to the code
3. **Append updates** to session memory
4. **Update common/CHANGES.md** if changes affect multiple components
5. **Test** the changes
6. **Commit** with descriptive message

---

## 🐛 Troubleshooting

See **[infra/README.md](./infra/README.md)** for detailed troubleshooting guide.

---

## 📝 Contributing

1. Read relevant `SESSION_MEMORY.md` file
2. Read `common/CHANGES.md` for recent cross-component changes
3. Create feature branch
4. Make changes and update documentation
5. Write tests
6. Submit PR

---

## 🔗 Related Documentation

- **Root README**: [../../README.md](../../README.md)
- **Project Status**: [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md)
- **Old Architecture**: [../old app/](../old%20app/)

---

## 🛡️ Revolutionary Zero-Downtime Features (Competitive Moat)

### Five-Layer Defense Strategy (Safety Enforcement)
CloudOptim implements a **mandatory safety validation layer** between ML recommendations and execution:

1. **Risk Threshold Validation** - All Spot instance pools must have risk scores ≥0.75
2. **AZ Distribution Validation** - Minimum 3 availability zones required
3. **Pool Concentration Validation** - Maximum 20% allocation per instance pool
4. **On-Demand Buffer Validation** - Minimum 15% On-Demand capacity always maintained
5. **Multi-Factor Validation** - All constraints must pass simultaneously

**Key Components:**
- `SafetyEnforcer` (core-platform/services/safety_enforcer.py) - Validates all recommendations
- `SafeExecutor` (core-platform/services/safe_executor.py) - Wraps ML Server calls with mandatory validation
- Database audit trail in `safety_violations` table
- Safe alternatives automatically created when violations detected

**Result**: Zero unsafe deployments, automatic fallback to safe configurations

### Customer Feedback Loop - The Competitive Moat
CloudOptim learns from **real Spot interruptions** to build insurmountable competitive advantage.

#### V2.0: Cross-Client Learning & Network Effect 🚀
**Revolutionary Architecture**: First clients act as "canaries" to protect remaining clients through proactive rebalancing.

**How It Works:**
1. **2 clients** get interruption in same pool → Pool flagged as **UNCERTAIN**
2. **3+ clients** affected → Pool confirmed as **RISKY**
3. System **proactively rebalances** all remaining clients BEFORE they get termination notices
4. First clients validate predictions, remaining clients protected

**Example Scenario:**
```
Client 1 → Interruption in m5.large/us-east-1a (NORMAL)
Client 2 → Same pool interruption → Flag as UNCERTAIN (+0.10 risk)
Client 3 → Same pool interruption → Confirm RISKY (+0.20 risk)
         → Identify 50 other clients in this pool
         → Create proactive rebalance jobs for all 50
         → Move them to safer pools BEFORE termination
Result: First 3 clients = canaries, 50 clients = protected
```

**Learning Timeline:**
- **Month 1** (0-10K instance-hours): 0% weight - Using AWS Spot Advisor only
- **Month 3** (10K-50K): 10% weight - Early patterns detected
- **Month 6** (50K-200K): 15% weight - Temporal/workload patterns clear
- **Month 12+** (500K+ instance-hours): 25% weight - **COMPETITIVE MOAT ACHIEVED**

**Network Effect:**
```
Single Client:  12 months to reach 500K instance-hours
100 Clients:    3 months to reach 500K collective hours
→ 4x faster competitive moat through collective learning
```

**Adaptive Risk Formula:**
```
Month 1:  Risk = 60% AWS + 30% Volatility + 10% Structural + 0% Customer
Month 12: Risk = 35% AWS + 30% Volatility + 25% Customer + 10% Structural
```

**Key Components:**
- Feedback API (ml-server/backend/api/routes/feedback.py) - 6 endpoints for interruption ingestion
- Cross-Client Learning Service (ml-server/backend/services/feedback_service.py) - Pattern detection across customers
- Adaptive Spot Optimizer (ml-server/decision_engine/spot_optimizer.py) - Uses collective feedback
- Database tables: `interruption_feedback`, `risk_score_adjustments`, `feedback_learning_stats`, `proactive_rebalance_jobs`

**Patterns Detected:**
- Temporal patterns (day_of_week, hour_of_day)
- Workload patterns (web, database, ml, batch)
- Seasonal patterns (Black Friday, end-of-quarter)
- AZ-specific patterns
- **Cross-client patterns** (multiple customers affected simultaneously)

**Competitive Advantage:**
After 500K+ instance-hours, competitors **cannot replicate** this data advantage:
- Our risk scores are 25% based on real customer interruptions
- Cross-client learning creates exponential advantage (more customers = better protection)
- Network effect: New customers immediately benefit from existing customer data
- Competitors stuck with 100% AWS Spot Advisor + single-client learning

### Hybrid Rightsizing Engine (Day Zero Ready)
CloudOptim's rightsizing works **immediately on Day Zero** and improves over time:

**Phase 1: Deterministic (Month 0-3)**
- Comprehensive lookup tables for 20+ instance types
- Usage-based rules: Downsize if <50%, upsize if >80%
- Workload-specific recommendations (web, database, ml, batch, cache)
- 20% safety buffer for spikes
- Confidence: 0.75-0.85

**Phase 2: ML Enhanced (Month 3+)**
- Time series forecasting for usage spikes
- Temporal pattern integration
- Workload pattern integration
- Merge logic: Safety-first (use ML if predicts larger)
- Confidence: 0.85-0.95

**Key Features:**
- Instance lookup table with pricing tiers
- Cost optimization (choose lowest cost option)
- Constraint enforcement (min/max CPU/memory, allowed/blocked types)
- Phased execution planning with rollback procedures
- Manual review flagging when predictions diverge >30%

**Components:**
- Rightsizing Engine (ml-server/decision_engine/rightsizing.py) - 743 lines of production code
- Execution planner with pre-flight checks, downsizes first, then upsizes
- Monthly savings calculations

---

## 🔗 Enhanced API Endpoints

### ML Server - Feedback Loop (Port 8001)
```
POST /api/v1/ml/feedback/interruption       - Ingest Spot interruption data
GET  /api/v1/ml/feedback/patterns/{type}    - Get learned patterns
GET  /api/v1/ml/feedback/stats              - Global learning statistics
GET  /api/v1/ml/feedback/weight             - Current customer feedback weight
```

---

**Last Updated**: 2025-12-01
**Status**: ✅ Complete Implementation with Revolutionary Features
- ✅ ML Server (76 files, 8 decision engines, feedback loop)
- ✅ Core Platform (48 files, agentless architecture, safety enforcement)
- ✅ Five-Layer Defense Strategy (zero unsafe deployments)
- ✅ Customer Feedback Loop (competitive moat at 500K+ instance-hours)
- ✅ Hybrid Rightsizing Engine (Day Zero ready, ML enhanced at Month 3+)
- ✅ Common (schemas, auth, config)
- ✅ Infrastructure (docker-compose, k8s manifests)
- ✅ Comprehensive test suite (600+ test cases)
