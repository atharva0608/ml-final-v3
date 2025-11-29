# CloudOptim - Cross-Component Changes Log

**Purpose**: Track all changes that affect multiple components or require coordinated updates across the system.

**How to Use This File**:
1. **Before making changes**: Check this log to understand recent cross-component updates
2. **After making changes**: Log any change that affects multiple components
3. **During development**: Reference this when implementing features that touch ML Server, Core Platform, or Frontend

**Change Format**:
```
## [Version/Date] - Change Type: Brief Title

**Components Affected**: [ML Server / Core Platform / Frontend / All]
**Change Type**: [Feature / Bugfix / Breaking Change / Architecture / Security / Performance]
**Developer Action Required**: [Yes/No]

### Description
Detailed description of what changed and why.

### Cross-Component Impact
- **ML Server**: What changed or what needs to be updated
- **Core Platform**: What changed or what needs to be updated
- **Frontend**: What changed or what needs to be updated

### Migration Steps (if breaking change)
1. Step-by-step migration instructions

### Related Commits
- `commit-hash` - Component name: commit message
```

---

## Recent Changes

---

## [2025-11-28] - Architecture: Removed SPS Scores, Use AWS Spot Advisor Only

**Components Affected**: ML Server, Core Platform, All Documentation
**Change Type**: Architecture / Breaking Change
**Developer Action Required**: Yes

### Description
User explicitly requested **NOT** to use AWS GetSpotPlacementScores (SPS). Removed all SPS score references and switched to AWS Spot Advisor public JSON data.

**Data Source Change**:
- ❌ **OLD**: `GetSpotPlacementScores` API (requires AWS credentials, not public)
- ✅ **NEW**: AWS Spot Advisor JSON (`https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json`)

### Cross-Component Impact

- **ML Server**:
  - `decision_engine/spot_optimizer.py`: Use public Spot Advisor data instead of SPS
  - `backend/aws_fetcher.py`: Remove `GetSpotPlacementScores` API calls
  - Risk score formula updated to use public interruption rates

- **Core Platform**:
  - IAM permissions: Removed `ec2:GetSpotPlacementScores` from required permissions
  - `services/aws_client.py`: Remove SPS-related methods
  - Documentation: Updated IAM policy examples

- **Frontend**:
  - No changes required (API responses remain compatible)

### Migration Steps

1. **ML Server Developer**:
   ```bash
   # Remove SPS API calls
   # Update spot_optimizer.py to use Spot Advisor JSON
   # Test risk score calculation with public data
   ```

2. **Core Platform Developer**:
   ```bash
   # Update IAM role templates
   # Remove SPS permissions from customer onboarding scripts
   ```

3. **DevOps**:
   ```bash
   # Update CloudFormation/Terraform templates
   # Remove ec2:GetSpotPlacementScores from IAM policies
   ```

### Related Commits
- `ff1d018` - ML Server: Add complete CAST AI feature set to ML Server decision engines
- `ff1d018` - Core Platform: Remove SPS score references from memory

---

## [2025-11-28] - Feature: Added All 8 CAST AI Decision Engines to ML Server

**Components Affected**: ML Server
**Change Type**: Feature
**Developer Action Required**: Yes (implementation required)

### Description
Added comprehensive documentation for all 8 CAST AI competitor features. All decision engines live in ML Server (NOT Core Platform).

**Decision Engines Added**:
1. **Spot Optimizer**: Risk-based Spot instance selection (AWS Spot Advisor)
2. **Bin Packing**: Tetris algorithm for workload consolidation
3. **Rightsizing**: Deterministic lookup tables for instance sizing
4. **Office Hours Scheduler**: Time-based auto-scaling for dev/staging
5. **Ghost Probe Scanner**: Zombie EC2 instance detection
6. **Zombie Volume Cleanup**: Unattached EBS volume cleanup
7. **Network Optimizer**: Cross-AZ traffic affinity optimization
8. **OOMKilled Remediation**: Auto-fix memory limits for OOMKilled pods

### Cross-Component Impact

- **ML Server**:
  - New files required in `decision_engine/`:
    ```
    spot_optimizer.py
    bin_packing.py
    rightsizing.py
    scheduler.py
    ghost_probe.py
    volume_cleanup.py
    network_optimizer.py
    oomkilled_remediation.py
    ```
  - New API endpoints (8 total):
    ```
    POST /api/v1/ml/decision/spot-optimize
    POST /api/v1/ml/decision/bin-pack
    POST /api/v1/ml/decision/rightsize
    POST /api/v1/ml/decision/schedule
    POST /api/v1/ml/decision/ghost-probe
    POST /api/v1/ml/decision/volume-cleanup
    POST /api/v1/ml/decision/network-optimize
    POST /api/v1/ml/decision/oomkilled-remediate
    ```

- **Core Platform**:
  - `services/ml_client.py`: Add methods to call new decision endpoints
  - `services/executor_service.py`: Execute recommendations from new engines
  - `services/data_collector.py`: Collect data for new engines (EC2 list, EBS volumes, pod events)

- **Frontend** (ML Server Frontend):
  - Add UI for uploading decision engine modules
  - Add controls for enabling/disabling each engine
  - Add dashboard widgets for each engine's savings

### Migration Steps

1. **ML Server Developer**:
   ```bash
   # Create base_engine.py with common interface
   # Implement each of the 8 decision engines
   # Add FastAPI routes for each engine
   # Write unit tests for each engine
   ```

2. **Core Platform Developer**:
   ```bash
   # Update ml_client.py with new decision methods
   # Implement data collection for ghost probe, volume cleanup
   # Add execution logic for all 8 engines
   ```

3. **Frontend Developer**:
   ```bash
   # Add engine upload component
   # Create dashboard widgets for new engines
   # Add savings visualization per engine
   ```

### Related Commits
- `ff1d018` - ML Server: Add complete CAST AI feature set to ML Server decision engines

---

## [2025-11-28] - Documentation: Added Installation Scripts to Component Memories

**Components Affected**: ML Server, Core Platform
**Change Type**: Documentation
**Developer Action Required**: No (optional testing)

### Description
Added comprehensive installation scripts to both component SESSION_MEMORY.md files. Scripts are based on old app setup scripts with production-tested versions.

**Installation Scripts**:
- `install_ml_server.sh` (390+ lines, 13 steps)
- `install_core_platform.sh` (280+ lines, 14 steps)

**Key Features**:
- Automated system dependency installation
- Python virtual environment setup
- PostgreSQL 15+ database creation
- Redis configuration
- Systemd service setup
- Nginx reverse proxy configuration
- Helper scripts (start, stop, status, logs)

### Cross-Component Impact

- **ML Server**:
  - New installation script in SESSION_MEMORY.md (lines 840-1184)
  - Dependencies: Python 3.11, PostgreSQL 15, Redis 7, Node.js 20.x
  - Systemd service: `ml-server-backend.service`
  - Ports: Backend 8001, Frontend 3001

- **Core Platform**:
  - New installation script in SESSION_MEMORY.md (lines 396-686)
  - Additional dependencies: kubectl (for remote K8s API)
  - Systemd service: `core-platform-backend.service`
  - Ports: Backend 8000, Frontend 80

- **Frontend**:
  - No changes required

### Version Reference (Production-Tested)

```txt
# System
Python: 3.11
PostgreSQL: 15+
Redis: 7+
Node.js: 20.x LTS
Nginx: 1.18+

# Python ML Stack
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
xgboost==1.7.6
lightgbm==4.0.0

# Python API
fastapi==0.103.0
uvicorn==0.23.2
Flask==3.0.0

# AWS & K8s
boto3==1.28.25
kubernetes==27.2.0

# Database & Cache
asyncpg==0.29.0
redis==5.0.0
```

### Migration Steps

**Optional Testing**:
1. Create test EC2 instances (Ubuntu 22.04/24.04)
2. Run installation scripts
3. Verify services start correctly
4. Test health check endpoints
5. Update scripts if issues found

### Related Commits
- `570ab3a` - Both Components: Add comprehensive installation & setup scripts to component memories

---

## [2025-11-28] - Documentation: WebSocket Architecture for Real-Time Updates

**Components Affected**: ML Server, Core Platform, Frontend
**Change Type**: Documentation
**Developer Action Required**: No (already implemented)

### Description
Clarified WebSocket usage for real-time dashboard updates and prediction tickers.

**WebSocket Endpoints**:
- `WS /api/v1/ml/stream` - ML Server → Frontend (live predictions)
- `WS /api/v1/admin/live-updates` - Core Platform → Admin Frontend (cost monitoring)

**Use Cases**:
- Real-time Spot interruption prediction tickers
- Live cost savings updates
- Cluster state changes
- Optimization execution progress

### Cross-Component Impact

- **ML Server**:
  - WebSocket endpoint: `/api/v1/ml/stream`
  - Library: socket.io (Python backend)
  - Data: Prediction streams, model inference results

- **Core Platform**:
  - WebSocket endpoint: `/api/v1/admin/live-updates`
  - Library: socket.io (Python backend)
  - Data: Cost savings, cluster metrics, execution status

- **Frontend** (Both ML Server and Core Platform):
  - Library: socket.io-client (JavaScript)
  - Framework: React 18+ with live chart updates
  - Charts: Recharts for predictions vs actual comparison

### Implementation Notes

**Backend (FastAPI/Flask)**:
```python
from socketio import AsyncServer

sio = AsyncServer(async_mode='asgi', cors_allowed_origins='*')

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

@sio.event
async def prediction_stream(sid, data):
    # Stream predictions to frontend
    await sio.emit('prediction_update', prediction_data, room=sid)
```

**Frontend (React)**:
```javascript
import { io } from 'socket.io-client';

const socket = io('ws://ml-server:8001');

socket.on('prediction_update', (data) => {
  // Update live chart
  updatePredictionChart(data);
});
```

### Related Commits
- No new commits (documentation only)

---

## Change Tracking Conventions

### When to Log a Change

**ALWAYS log if**:
- Change affects 2+ components
- API contract changes (request/response schemas)
- Database schema changes
- Environment variable changes
- Dependency version updates
- Security or permission changes
- Breaking changes to any interface

**OPTIONAL to log if**:
- Internal refactoring within one component
- UI-only changes (no backend impact)
- Documentation updates (unless architecture changes)
- Bug fixes that don't affect APIs

### Change Categories

| Type | Description | Examples |
|------|-------------|----------|
| **Feature** | New functionality | New decision engine, new API endpoint |
| **Bugfix** | Fixes broken functionality | Fix calculation error, fix API response |
| **Breaking Change** | Requires migration | API schema change, removal of feature |
| **Architecture** | System design changes | Switch from agent to agentless, new data source |
| **Security** | Security updates | IAM permission changes, authentication changes |
| **Performance** | Optimization | Database indexing, caching strategy |
| **Documentation** | Docs only | Installation guides, API documentation |

### Developer Workflow

**Before Starting Work**:
```bash
# 1. Pull latest changes
git pull origin claude/continue-context-analysis-01TxsNrQhh2W2J2Sy4vX5fpR

# 2. Read CHANGES.md
cat "new app/common/CHANGES.md"

# 3. Check component-specific memory
cat "new app/ml-server/SESSION_MEMORY.md"
```

**After Completing Work**:
```bash
# 1. Update component memory file
vim "new app/ml-server/SESSION_MEMORY.md"

# 2. If change affects other components, update CHANGES.md
vim "new app/common/CHANGES.md"

# 3. Commit with descriptive message
git add .
git commit -m "ML Server: Add new decision engine for cost optimization"
git push -u origin claude/continue-context-analysis-01TxsNrQhh2W2J2Sy4vX5fpR
```

---

## Quick Reference

### Component Ports
- **ML Server Backend**: 8001
- **ML Server Frontend**: 3001
- **Core Platform Backend**: 8000
- **Core Platform Frontend**: 80

### Component Responsibilities
- **ML Server**: Makes ALL decisions, hosts models, decision engines, pricing data
- **Core Platform**: Executes decisions, interacts with AWS/K8s APIs, no decision logic
- **Frontend (ML)**: Model upload, decision engine management, prediction monitoring
- **Frontend (Admin)**: Cost monitoring, cluster management, optimization history

### Critical Architecture Principles
1. **Agentless**: No DaemonSets, no client-side components
2. **ML-Driven**: ALL decisions made by ML Server
3. **Remote APIs**: Core Platform uses remote K8s API + AWS APIs
4. **Event-Based**: AWS EventBridge + SQS for Spot warnings
5. **Public Data**: AWS Spot Advisor JSON (NO SPS scores)

---

## [2025-11-29] - Feature: Core Platform Complete Implementation with Enhanced UX

**Components Affected**: Core Platform, ML Server (Integration), Admin Frontend
**Change Type**: Feature / Architecture
**Developer Action Required**: Yes (deployment required)

### Description

Completed full implementation of Core Platform with agentless architecture and enhanced admin frontend. Built 48 files across 24 directories implementing all services, APIs, and frontend components.

**Key Implementations**:
1. **Agentless Architecture Services**: Remote K8s API client, SQS poller, Spot handler
2. **Enhanced Admin Frontend**: Modern dark theme, Framer Motion animations, interactive Recharts
3. **ML Server Integration**: Full integration client with all 8 decision engine endpoints
4. **AWS Integration**: EC2 management, EventBridge + SQS for Spot warnings
5. **Complete Backend**: FastAPI with lifespan management, database models, health checks

**Enhanced UX Features (10 Major Improvements)**:
1. **Professional Dark Theme**: Custom color palette (#0A1929 background, #00C853 success green)
2. **Animated Components**: Framer Motion for smooth transitions and entrance animations
3. **Interactive Charts**: Recharts dual-area charts, pie charts, bar charts with gradients
4. **Gradient Stat Cards**: Animated statistics cards with trend indicators (+14.5% vs last month)
5. **Loading States**: Skeleton loaders and spinner animations
6. **Responsive Layout**: Mobile-first Grid system with breakpoints
7. **Visual Depth**: Box shadows, elevated surfaces, layered components
8. **Real-Time Updates**: React Query for automatic data refresh (30s intervals)
9. **Formatted Numbers**: numeral.js for currency ($10,234) and percentages (14.5%)
10. **Error Boundaries**: Graceful error handling with user-friendly messages

### Cross-Component Impact

- **Core Platform**:
  - **Backend** (`/backend/`):
    - `main.py`: FastAPI app with lifespan management (startup: SQS poller, K8s clients, ML Server connection)
    - `database/models.py`: 8 tables (clusters, nodes, spot_warnings, optimization_history, pod_events, ml_decisions, cost_savings, api_keys)
    - `api/routes/`: 5 route modules (clusters, nodes, spot_warnings, optimization, ml_integration)

  - **Services** (`/services/`):
    - `k8s_remote_client.py`: Remote Kubernetes API (NO agents) - drain, cordon, evict, list operations
    - `eventbridge_poller.py`: SQS polling every 5 seconds for Spot interruption warnings
    - `spot_handler.py`: Handles Spot warnings with 60-second grace period drain + ML recommendation
    - `ml_client.py`: Client for all 8 ML Server decision endpoints (spot-optimize, bin-pack, etc.)
    - `aws_client.py`: EC2 instance management (launch, terminate, describe)

  - **Admin Frontend** (`/admin-frontend/`):
    - `App.tsx`: Dark theme, React Router, React Query provider, MUI theming
    - `components/Dashboard/Overview.tsx`: 4 animated stat cards, savings trend chart, cost breakdown pie
    - `components/Clusters/ClusterList.tsx`: Table with Spot/On-Demand counts, auto-scaling status
    - `components/Navigation.tsx`: Modern nav bar with routing
    - `services/api.ts`: Typed API client with interfaces for all endpoints

  - **Configuration**:
    - Port 8000 (backend), Port 80 (frontend)
    - PostgreSQL 15+ database: `core_platform_db`
    - Redis cache for session management
    - Environment variables: AWS credentials, K8s configs, ML Server URL

- **ML Server**:
  - **Integration Points** (Core Platform → ML Server):
    - `POST /api/v1/ml/decision/spot-optimize`: Called by spot_handler on interruption warnings
    - `POST /api/v1/ml/decision/bin-pack`: Called by optimization scheduler for workload consolidation
    - `POST /api/v1/ml/decision/rightsize`: Called for instance sizing recommendations
    - All 8 decision engine endpoints now have active consumers

  - **Data Flow** (Core Platform → ML Server):
    ```
    Spot Warning (EventBridge) → SQS → Core Platform poller
    → spot_handler.handle_interruption()
    → ml_client.request_spot_optimization()
    → ML Server /api/v1/ml/decision/spot-optimize
    → ML Server responds with replacement recommendation
    → Core Platform executes via aws_client.launch_instance()
    ```

- **Frontend (Admin)**:
  - **Technology Stack**:
    - React 18.2.0 + TypeScript 5.0
    - Material-UI 5.14.0 (theming, components)
    - Recharts 2.8.0 (data visualization)
    - Framer Motion 10.16.0 (animations)
    - React Query 3.39.0 (data fetching)
    - React Router 6.15.0 (navigation)
    - numeral 2.0.6 (number formatting)

  - **Key Components**:
    ```
    src/
    ├── App.tsx (theme, routing, providers)
    ├── components/
    │   ├── Dashboard/Overview.tsx (stat cards, charts)
    │   ├── Clusters/ClusterList.tsx (cluster table)
    │   ├── Nodes/NodeList.tsx (node management)
    │   ├── Optimization/History.tsx (optimization logs)
    │   └── Navigation.tsx (nav bar)
    ├── services/api.ts (typed API client)
    └── types/index.ts (TypeScript interfaces)
    ```

### Architecture Compliance

**Agentless Architecture** ✅:
- NO DaemonSets or client-side agents
- Remote Kubernetes API via `kubernetes==27.2.0` client library
- All K8s operations via HTTPS API calls

**ML-Driven Decisions** ✅:
- Core Platform makes ZERO decisions autonomously
- All optimization logic delegated to ML Server
- Core Platform acts as "executor" only

**Event-Based Spot Handling** ✅:
- AWS EventBridge → SQS → Core Platform poller (5-second intervals)
- Spot warnings trigger drain + ML recommendation + replacement launch
- 60-second grace period for pod eviction (within 2-minute Spot warning window)

**Remote API Operations** ✅:
- Kubernetes: Remote API via kubeconfig
- AWS: boto3 SDK for EC2, SQS operations
- No local agents, no SSH, no node-level access

**Public Data Sources** ✅:
- AWS Spot Advisor JSON (no SPS scores)
- EC2 pricing API
- CloudWatch metrics

### Directory Structure Created

```
core-platform/
├── backend/                    # FastAPI application (8000)
│   ├── main.py                # Lifespan: SQS poller, K8s clients, ML connection
│   ├── api/routes/            # 5 route modules (clusters, nodes, spot, optimization, ml)
│   ├── database/              # SQLAlchemy models (8 tables)
│   └── schemas/               # Pydantic schemas (8 schemas)
├── services/                   # Core business logic
│   ├── k8s_remote_client.py   # Remote K8s API (drain, cordon, evict)
│   ├── eventbridge_poller.py  # SQS polling for Spot warnings
│   ├── spot_handler.py        # Spot interruption handler (drain + ML + launch)
│   ├── ml_client.py           # ML Server integration (8 decision endpoints)
│   └── aws_client.py          # AWS EC2 management
├── admin-frontend/             # React 18 + TypeScript
│   ├── src/
│   │   ├── App.tsx            # Dark theme, routing, providers
│   │   ├── components/        # Dashboard, Clusters, Nodes, Optimization, Navigation
│   │   ├── services/api.ts    # Typed API client
│   │   └── types/index.ts     # TypeScript interfaces
│   └── package.json           # React 18, MUI 5, Recharts, Framer Motion, React Query
├── config/
│   ├── settings.py            # Pydantic settings (env vars)
│   └── logging_config.py      # Structured logging
├── scripts/
│   ├── setup_db.py            # Database initialization
│   ├── seed_data.py           # Sample data
│   └── test_k8s_connection.py # K8s connectivity test
├── tests/
│   ├── test_k8s_client.py     # Remote K8s API tests
│   ├── test_services.py       # Service layer tests
│   └── test_api.py            # API endpoint tests
├── docs/
│   ├── API_SPEC.md            # OpenAPI/Swagger docs
│   └── DEPLOYMENT.md          # Deployment guide
├── requirements.txt            # Python dependencies
├── README.md                   # Setup guide (320 lines)
└── SESSION_MEMORY.md          # Implementation log (1409 lines)
```

**Total Files Created**: 48 files across 24 directories

### Key Code Implementations

**1. Agentless K8s Remote Client** (`services/k8s_remote_client.py`):
```python
class K8sRemoteClient:
    def __init__(self, kubeconfig_path: str):
        config.load_kube_config(config_file=kubeconfig_path)
        self.core_v1 = k8s_client.CoreV1Api()
        self.apps_v1 = k8s_client.AppsV1Api()

    def drain_node(self, node_name: str, grace_period_seconds: int = 90):
        # 1. Cordon node (remote API call)
        self.cordon_node(node_name)
        # 2. List all pods on the node
        pods = self.core_v1.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={node_name}"
        )
        # 3. Evict each pod (remote eviction API)
        for pod in pods.items:
            eviction = k8s_client.V1Eviction(
                metadata=k8s_client.V1ObjectMeta(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace
                ),
                delete_options=k8s_client.V1DeleteOptions(
                    grace_period_seconds=grace_period_seconds
                )
            )
            self.core_v1.create_namespaced_pod_eviction(...)
```

**2. EventBridge SQS Poller** (`services/eventbridge_poller.py`):
```python
async def start(self, queue_configs: List[Dict]):
    self.running = True
    while self.running:
        await self._poll_all_queues(queue_configs)
        await asyncio.sleep(self.poll_interval)  # 5 seconds

async def _poll_all_queues(self, queue_configs):
    for config in queue_configs:
        messages = await self._receive_messages(config['queue_url'])
        for msg in messages:
            event = json.loads(msg['Body'])
            if event['detail-type'] == 'EC2 Spot Instance Interruption Warning':
                await self.callback_handler(event)
```

**3. Enhanced Dashboard with Animations** (`admin-frontend/src/components/Dashboard/Overview.tsx`):
```tsx
// Animated stat card with gradient and trend
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  <Card sx={{ background: 'linear-gradient(135deg, #00C853 0%, #00E676 100%)' }}>
    <CardContent>
      <AttachMoney sx={{ fontSize: 40, color: 'white' }} />
      <Typography variant="h4" color="white">$10,234</Typography>
      <Typography variant="caption" color="rgba(255,255,255,0.8)">
        Monthly Savings
      </Typography>
      <Chip
        label="+14.5% vs last month"
        size="small"
        sx={{ bgcolor: 'rgba(255,255,255,0.2)' }}
      />
    </CardContent>
  </Card>
</motion.div>

// Dual-area chart with gradients
<AreaChart data={savingsData}>
  <defs>
    <linearGradient id="colorSavings" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#00C853" stopOpacity={0.8}/>
      <stop offset="95%" stopColor="#00C853" stopOpacity={0}/>
    </linearGradient>
  </defs>
  <Area
    type="monotone"
    dataKey="savings"
    stroke="#00C853"
    fill="url(#colorSavings)"
  />
  <Area
    type="monotone"
    dataKey="predicted"
    stroke="#2196F3"
    fill="url(#colorPredicted)"
  />
</AreaChart>
```

**4. ML Server Integration Client** (`services/ml_client.py`):
```python
class MLServerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def request_spot_optimization(self, cluster_state, requirements, constraints):
        response = await self.client.post(
            f"{self.base_url}/api/v1/ml/decision/spot-optimize",
            json={"cluster_state": cluster_state, "requirements": requirements, "constraints": constraints}
        )
        return response.json()

    async def request_bin_packing(self, pods, available_nodes):
        response = await self.client.post(
            f"{self.base_url}/api/v1/ml/decision/bin-pack",
            json={"pods": pods, "available_nodes": available_nodes}
        )
        return response.json()

    # + 6 more decision engine methods (rightsize, schedule, ghost-probe, etc.)
```

**5. FastAPI Lifespan Management** (`backend/main.py`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Core Platform Starting...")

    # Initialize database
    await init_db()

    # Initialize Redis cache
    await init_redis()

    # Connect to ML Server
    ml_client = MLServerClient(base_url=settings.ML_SERVER_URL)
    app.state.ml_client = ml_client

    # Initialize K8s clients (one per cluster)
    app.state.k8s_clients = {}
    for cluster_config in settings.CLUSTERS:
        k8s_client = K8sRemoteClient(kubeconfig_path=cluster_config['kubeconfig'])
        app.state.k8s_clients[cluster_config['cluster_id']] = k8s_client

    # Start SQS poller for Spot warnings
    poller = EventBridgePoller(callback_handler=handle_spot_warning)
    asyncio.create_task(poller.start(queue_configs=settings.SQS_QUEUES))
    app.state.poller = poller

    logger.info("Core Platform Ready!")

    yield  # Application runs here

    # Shutdown: Stop SQS poller, close connections
    logger.info("Core Platform Shutting Down...")
    poller.stop()
    await ml_client.close()
```

### Migration Steps

**1. Deploy Core Platform Backend**:
```bash
cd "/home/user/ml-final-v3/new app/core-platform"

# Install dependencies
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup database
python scripts/setup_db.py

# Configure environment
cp .env.example .env
# Edit .env: Set ML_SERVER_URL, AWS credentials, K8s configs, PostgreSQL

# Start backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**2. Deploy Admin Frontend**:
```bash
cd "/home/user/ml-final-v3/new app/core-platform/admin-frontend"

# Install dependencies
npm install

# Configure API endpoint
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# Start development server
npm start

# Production build
npm run build
# Serve build/ with Nginx on port 80
```

**3. Configure AWS EventBridge + SQS**:
```bash
# Create SQS queue for Spot warnings
aws sqs create-queue --queue-name cloudoptim-spot-warnings

# Create EventBridge rule for EC2 Spot interruptions
aws events put-rule \
  --name cloudoptim-spot-interruption-rule \
  --event-pattern '{"source":["aws.ec2"],"detail-type":["EC2 Spot Instance Interruption Warning"]}'

# Add SQS as target
aws events put-targets \
  --rule cloudoptim-spot-interruption-rule \
  --targets "Id"="1","Arn"="arn:aws:sqs:us-east-1:ACCOUNT_ID:cloudoptim-spot-warnings"
```

**4. Configure Kubernetes Access**:
```bash
# Download kubeconfig for each cluster
aws eks update-kubeconfig --name production-cluster --region us-east-1

# Test connectivity
python scripts/test_k8s_connection.py

# Add kubeconfig path to .env
echo "KUBECONFIG_PRODUCTION=/home/user/.kube/config-production" >> .env
```

**5. Test Integration with ML Server**:
```bash
# Health check
curl http://localhost:8000/health

# Test ML Server connectivity
curl http://localhost:8000/api/v1/ml/health

# Trigger test optimization
curl -X POST http://localhost:8000/api/v1/optimization/trigger \
  -H "Content-Type: application/json" \
  -d '{"cluster_id": "test-cluster", "optimization_type": "spot"}'
```

### Testing Checklist

- [ ] Backend health check returns 200 OK
- [ ] PostgreSQL database tables created (8 tables)
- [ ] Redis connection successful
- [ ] K8s remote API connectivity (can list nodes)
- [ ] SQS poller receiving messages
- [ ] ML Server integration (can call decision endpoints)
- [ ] AWS EC2 API access (can describe instances)
- [ ] Admin frontend loads without errors
- [ ] Dashboard charts render with mock data
- [ ] Cluster list displays connected clusters
- [ ] Navigation between pages works
- [ ] Dark theme renders correctly
- [ ] Animations play smoothly

### Related Commits

- `7702724` - Core Platform: Complete implementation with all 8 CAST AI engines
- `23e2fd7` - Common: Add common changes tracking system for cross-component coordination
- `570ab3a` - Core Platform: Add comprehensive installation & setup scripts to component memories

### Breaking Changes

**None** - This is a new implementation. No existing functionality affected.

### Security Considerations

**AWS IAM Permissions Required**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:DescribeSpotPriceHistory",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "*"
    }
  ]
}
```

**Kubernetes RBAC Required**:
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cloudoptim-core-platform
rules:
- apiGroups: [""]
  resources: ["nodes", "pods", "pods/eviction"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "statefulsets", "daemonsets"]
  verbs: ["get", "list", "watch", "update", "patch"]
```

**Network Security**:
- Core Platform → ML Server: HTTPS/TLS (port 8001)
- Core Platform → K8s API: HTTPS/TLS (port 6443)
- Core Platform → AWS APIs: HTTPS/TLS (443)
- Admin Frontend → Core Platform: HTTPS/TLS (port 8000)

### Performance Benchmarks

**Expected Performance**:
- Spot Warning Response Time: < 5 seconds (from SQS message to drain start)
- Node Drain Time: 60 seconds (grace period)
- ML Decision Latency: < 2 seconds (per optimization request)
- Dashboard Load Time: < 1 second (initial load)
- Chart Render Time: < 100ms (with 1000 data points)

**Resource Requirements**:
- CPU: 2 cores (backend), 1 core (frontend build)
- Memory: 2GB (backend), 512MB (frontend)
- Database: PostgreSQL 15+ with 10GB storage
- Redis: 512MB cache

---

**Last Updated**: 2025-11-29
**Maintained By**: Development Team
**Location**: `new app/common/CHANGES.md`
