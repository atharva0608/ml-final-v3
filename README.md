# CloudOptim: Intelligent Kubernetes Cost Optimization Platform

**Version**: 1.0.0
**Created**: 2025-11-28
**Architecture**: Multi-Server Microservices

---

## 🎯 Project Overview

CloudOptim is an agentless, AI-powered Kubernetes cost optimization platform that reduces cloud infrastructure costs by 60-80% while maintaining application reliability. The platform operates as an external control plane with three main components running on separate instances.

### Key Features
- **Spot Instance Optimization**: Intelligent Spot instance selection with <5% interruption risk
- **Bin Packing**: Automated workload consolidation to minimize node count
- **Rightsizing**: Match instance sizes to actual workload requirements
- **Office Hours Scheduling**: Auto-scale dev/staging environments
- **Real-time Cost Monitoring**: Live dashboard showing predictions vs actual costs
- **Data Gap Filling**: Handle scenario where model is trained on old data but needs recent data

### Competitive Advantages
- ✅ **No "Cold Start"**: Uses public AWS data for immediate value (Day 1)
- ✅ **Agentless**: Minimal footprint on customer clusters
- ✅ **Public Data Foundation**: Not dependent on months of customer data collection
- ✅ **Pluggable Architecture**: Easy to extend with new optimization engines

---

## 🏗️ Architecture

### Three-Component Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   ML Server      │     │ Central Server   │     │  Client Agent    │
│  (Instance 1)    │◄───►│  (Instance 2)    │◄───►│ (Customer K8s)   │
│                  │     │                  │     │                  │
│ • ML Models      │     │ • REST API       │     │ • Task Executor  │
│ • Decision       │     │ • PostgreSQL     │     │ • Metrics        │
│   Engines        │     │ • Admin UI       │     │   Collector      │
│ • Data Fetcher   │     │ • Orchestrator   │     │ • Event Watcher  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

---

## 📁 Project Structure

```
ml-final-v3/
├── README.md                          # This file
├── common/                            # Shared components across all servers
│   ├── INTEGRATION_GUIDE.md          # ⭐ Integration documentation
│   ├── schemas/                       # Shared Pydantic models
│   ├── auth/                          # Authentication middleware
│   └── config/                        # Common configuration
│
├── ml-server/                         # Machine Learning & Decision Engine
│   ├── SESSION_MEMORY.md             # ⭐ ML Server session documentation
│   ├── models/                        # ML models
│   ├── decision_engine/               # Pluggable decision engines
│   ├── data/                          # Data fetching and gap filling
│   ├── api/                           # FastAPI server
│   └── scripts/                       # Installation scripts
│
├── central-server/                    # Backend, Database, Admin Frontend
│   ├── SESSION_MEMORY.md             # ⭐ Central Server session documentation
│   ├── api/                           # FastAPI application
│   ├── database/                      # PostgreSQL schema & migrations
│   ├── admin-frontend/                # React admin dashboard
│   ├── services/                      # Business logic services
│   └── scripts/                       # Deployment scripts
│
└── client-server/                     # Client-Side Agent
    ├── SESSION_MEMORY.md             # ⭐ Client Server session documentation
    ├── agent/                         # Agent implementation
    ├── tasks/                         # Task executors
    ├── deployment.yaml                # Kubernetes deployment
    └── scripts/                       # Installation scripts
```

---

## 📖 Documentation Guide

### Session Memory Documents
Each server component has a detailed `SESSION_MEMORY.md` file that contains:
- Component overview and responsibilities
- Integration points with other servers
- Directory structure
- Technology stack
- Deployment configuration
- Session updates log (append new changes here)

**⭐ READ THESE FIRST**:
1. [`ml-server/SESSION_MEMORY.md`](./ml-server/SESSION_MEMORY.md)
2. [`central-server/SESSION_MEMORY.md`](./central-server/SESSION_MEMORY.md)
3. [`client-server/SESSION_MEMORY.md`](./client-server/SESSION_MEMORY.md)
4. [`common/INTEGRATION_GUIDE.md`](./common/INTEGRATION_GUIDE.md)

### Working on Individual Components

When working on a specific component:
1. Read its `SESSION_MEMORY.md` file first
2. Make your changes
3. **Append updates** to the "Session Updates Log" section
4. Update integration points if APIs change
5. Keep common schemas synchronized

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- AWS Account (for production)
- Kubernetes cluster (for Client Agent)

### Installation

#### 1. ML Server
```bash
cd ml-server
./scripts/install.sh
./scripts/start_server.sh
```
Server will run on: `http://localhost:8001`

#### 2. Central Server
```bash
cd central-server
./scripts/setup_database.sh
./scripts/start_server.sh
./scripts/deploy_frontend.sh
```
- API: `http://localhost:8000`
- Admin UI: `http://localhost:3000`

#### 3. Client Agent (on Kubernetes)
```bash
cd client-server
./scripts/install.sh
```
Agent will deploy to `kube-system` namespace

### Docker Compose (Development)
```bash
docker-compose up -d
```

---

## 🔗 Common Components Integration

### Shared Data Schemas
All servers use common Pydantic models defined in `/common/schemas/`:
- `ClusterState` - Cluster state representation
- `DecisionRequest` - ML decision request format
- `DecisionResponse` - ML decision response format
- `Task` - Client task definition
- `TaskResult` - Task execution result
- `ClusterMetrics` - Metrics data

**⚠️ IMPORTANT**: When updating schemas, update all three servers to maintain compatibility.

### Authentication
All servers use API key authentication:
- Header: `Authorization: Bearer {API_KEY}`
- Implementation: `/common/auth/api_key.py`

### Configuration
Common configuration in `/common/config/common.yaml`:
- Database connection
- Redis connection
- Logging configuration
- API settings

---

## 📊 Key Features Detail

### 1. ML Model & Decision Engine

**Location**: `ml-server/`

**Components**:
- **Spot Predictor**: XGBoost model predicting Spot interruption probability
- **Spot Optimizer Engine**: Selects optimal Spot instances using risk scoring
- **Bin Packing Engine**: Consolidates workloads (TODO)
- **Rightsizing Engine**: Matches instance sizes to workloads (TODO)
- **Office Hours Scheduler**: Auto-scales based on schedule (TODO)

**Pluggable Architecture**:
All engines inherit from `BaseDecisionEngine` with fixed input/output contracts.

### 2. Central Backend & Database

**Location**: `central-server/`

**Components**:
- **REST API**: FastAPI server handling all orchestration
- **PostgreSQL Database**: Customer data, clusters, nodes, optimization history
- **Services**:
  - Optimizer Service (coordinates ML Server)
  - Executor Service (executes optimization plans)
  - Spot Handler (processes Spot interruptions)
  - K8s Client (remote cluster management)
  - AWS Client (EC2, SQS integration)

### 3. Admin Frontend

**Location**: `central-server/admin-frontend/`

**Features**:
- 📊 Real-time cost monitoring dashboard
- 📈 Prediction vs actual comparison charts
- 📤 Model upload interface
- 🔧 Data gap filling tool
- 📜 Optimization history
- ⚙️ Cluster configuration

**Tech Stack**: React + TypeScript + Material-UI

### 4. Client-Side Agent

**Location**: `client-server/`

**Deployment**: Runs as Kubernetes Deployment in customer cluster

**Responsibilities**:
- Poll Central Server for tasks (every 10s)
- Execute tasks: node draining, labeling, cordoning
- Collect and send cluster metrics (every 60s)
- Watch and forward Kubernetes events
- Report health status (heartbeat every 30s)

**Minimal Footprint**: 100m CPU, 128Mi RAM

---

## 🔄 Workflows

### Spot Optimization Workflow
```
1. Admin triggers optimization (or scheduled)
2. Central Server fetches cluster state
3. Central Server → ML Server: Decision request
4. ML Server: Analyze using SpotOptimizerEngine
5. ML Server → Central Server: Recommendations
6. Central Server: Validate and execute (launch Spot instances)
7. Central Server → Client Agent: Send tasks (drain nodes)
8. Client Agent: Execute tasks on Kubernetes
9. Central Server: Update database, calculate savings
10. Admin Dashboard: Display real-time savings
```

### Spot Interruption Handling
```
1. AWS EventBridge → SQS: Interruption warning (2-min notice)
2. Central Server polls SQS (every 5s)
3. Central Server: Identify affected node
4. Central Server → ML Server: Get replacement recommendation
5. Central Server: Launch On-Demand replacement (guaranteed)
6. Central Server → Client Agent: Drain dying node
7. Client Agent: Evict pods gracefully
8. New node joins cluster, pods reschedule
9. (Later) Replace On-Demand with Spot when safe
```

### Data Gap Filling
```
1. Admin uploads model trained on old data (e.g., 30 days ago)
2. Admin opens Gap Filler UI
3. UI queries required data range (e.g., last 15 days)
4. Central Server → ML Server: Identify gaps
5. ML Server: Calculate missing date ranges
6. ML Server: Query AWS APIs (Spot prices, interruption data)
7. ML Server: Fill missing data
8. Central Server: Store filled data in database
9. UI: Display success, show records filled
10. Model now has complete recent data for accurate predictions
```

---

## 🛠️ Technology Stack

### ML Server
- Python 3.10, FastAPI, XGBoost, scikit-learn
- boto3 (AWS), kubernetes-client
- Redis (caching)

### Central Server
- **Backend**: Python 3.10, FastAPI, SQLAlchemy
- **Database**: PostgreSQL 15, Redis 7
- **Frontend**: React 18 + TypeScript
- **Background Jobs**: Celery
- **AWS**: boto3, SQS, EventBridge

### Client Agent
- Python 3.10, asyncio, kubernetes-client
- Deployed as Kubernetes Deployment

---

## 📈 Performance Targets

- **Cost Reduction**: 60-80%
- **Spot Interruption Rate**: <5%
- **API Response Time**: <500ms (p95)
- **Decision Latency**: <2 seconds
- **Agent Footprint**: <128Mi RAM, <100m CPU

---

## 🧪 Testing

### Run All Tests
```bash
# ML Server
cd ml-server && pytest tests/

# Central Server
cd central-server && pytest tests/

# Client Agent
cd client-server && pytest tests/
```

### Integration Tests
```bash
# Requires all three servers running
pytest integration_tests/
```

---

## 🚢 Deployment

### Development
```bash
docker-compose up -d
```

### Production

#### ML Server
```bash
cd ml-server
./scripts/install.sh
./scripts/start_server.sh
```

#### Central Server
```bash
cd central-server
./scripts/setup_database.sh
./scripts/migrate_database.sh
./scripts/start_server.sh
./scripts/deploy_frontend.sh
```

#### Client Agent (per cluster)
```bash
kubectl apply -f client-server/deployment.yaml
```

---

## 📝 Development Workflow

### Adding a New Decision Engine

1. Create engine in `ml-server/decision_engine/`:
```python
from decision_engine.base_engine import BaseDecisionEngine

class MyNewEngine(BaseDecisionEngine):
    def analyze(self, input_data):
        # Implementation
        pass
```

2. Register in `ml-server/api/routes/decisions.py`

3. Update `ml-server/SESSION_MEMORY.md` (Session Updates Log section)

4. Update `common/INTEGRATION_GUIDE.md` if API changes

### Adding a New Task Type

1. Create task executor in `client-server/tasks/`:
```python
async def my_new_task(parameters: dict):
    # Implementation
    pass
```

2. Register in `client-server/agent/task_executor.py`

3. Update `client-server/SESSION_MEMORY.md`

4. Update common task schema in `common/schemas/tasks.py`

---

## 🐛 Troubleshooting

### ML Server not responding
- Check `ML_SERVER_URL` in Central Server config
- Verify ML Server is running: `curl http://localhost:8001/health`
- Check logs: `docker logs ml-server`

### Client Agent not executing tasks
- Check API key in Secret
- Verify RBAC permissions: `kubectl auth can-i create pods/eviction --as=system:serviceaccount:kube-system:cloudoptim-agent`
- Check logs: `kubectl logs -n kube-system deployment/cloudoptim-agent`

### Database connection errors
- Verify PostgreSQL is running
- Check connection string in config
- Test connection: `psql -h localhost -U central_server -d cloudoptim`

---

## 📞 Support

- **Documentation**: See individual `SESSION_MEMORY.md` files
- **Integration Issues**: See `common/INTEGRATION_GUIDE.md`
- **GitHub Issues**: [Create an issue](https://github.com/cloudoptim/platform/issues)

---

## 🗺️ Roadmap

### Phase 1 (Current)
- [x] Project structure created
- [x] Session memory documents
- [x] Common integration guide
- [ ] ML Server implementation
- [ ] Central Server implementation
- [ ] Client Agent implementation

### Phase 2
- [ ] Bin Packing Engine
- [ ] Rightsizing Engine
- [ ] Office Hours Scheduler
- [ ] Admin Frontend complete

### Phase 3
- [ ] Advanced ML models (deep learning)
- [ ] Multi-cloud support (GCP, Azure)
- [ ] Custom policies per customer
- [ ] Advanced analytics

---

## 📄 License

[To be determined]

---

## 🤝 Contributing

When contributing:
1. Read the relevant `SESSION_MEMORY.md` file
2. Make changes
3. Update session memory log
4. Update integration guide if APIs change
5. Add tests
6. Submit PR

---

**⭐ Remember**: Always update the `SESSION_MEMORY.md` file when working on a component!

**Last Updated**: 2025-11-28
