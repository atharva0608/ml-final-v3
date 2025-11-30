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

**Last Updated**: 2025-11-28
**Maintained By**: Development Team
**Location**: `new app/common/CHANGES.md`

---

## 2025-11-30 - ML Server: Added 4 Advanced Decision Engines + Model Training

**Component**: ML Server
**Type**: Feature Addition
**Impact**: Core Platform (API integration needed), Frontend (new UI components)

### Changes Made

#### 1. New Decision Engines (4 Advanced Features)

**Added Engines**:
1. **IPv4 Cost Tracker** - Track public IPv4 costs (NEW AWS charge Feb 2024)
2. **Container Image Bloat Tax** - Detect oversized container images  
3. **Shadow IT Tracker** - Find AWS resources NOT in Kubernetes
4. **Noisy Neighbor Detector** - Detect excessive network traffic

**API Impact** (Core Platform needs to implement):
```
# New decision endpoints required
POST /api/v1/ml/decision/ipv4-cost-tracking
POST /api/v1/ml/decision/image-bloat-analysis
POST /api/v1/ml/decision/shadow-it-detection
POST /api/v1/ml/decision/noisy-neighbor-detection

# New feature toggle endpoints
GET  /api/v1/ml/features/toggles
PUT  /api/v1/ml/features/toggles/{feature_name}
```

**Response Schema** (all decision endpoints):
```typescript
interface DecisionResponse {
  engine: string;
  recommendations: Recommendation[];
  confidence_score: number;  // 0.0-1.0
  estimated_savings: number;  // Monthly USD
  execution_plan: ExecutionStep[];
  metadata: {
    // Engine-specific metadata
    [key: string]: any;
  };
}

interface Recommendation {
  priority: "high" | "medium" | "low";
  category: string;
  // ... engine-specific fields
  monthly_cost?: number;
  annual_cost?: number;
  savings_monthly?: number;
  savings_annual?: number;
  action: string;
  description: string;
}
```

#### 2. Feature Toggles Configuration

**New Config Section** (`ml_config.yaml`):
```yaml
decision_engines:
  feature_toggles:
    ipv4_cost_tracking:
      enabled: true
      auto_scan_interval_hours: 24
    image_bloat_analysis:
      enabled: true
      auto_scan_interval_hours: 168
    shadow_it_detection:
      enabled: true
      auto_scan_interval_hours: 24
    noisy_neighbor_detection:
      enabled: true
      auto_scan_interval_hours: 6
```

**Core Platform Integration**:
- Core Platform should respect these toggles
- Check feature_toggles before calling decision endpoints
- Implement automated scanning based on auto_scan_interval_hours

#### 3. Model Training Infrastructure

**New Training Script**: `ml-server/training/train_models.py`
- Trains Spot Price Predictor models
- Outputs: model.pkl, metadata.json, scaler.pkl, label_encoders.pkl
- Hardware: Works on MacBook M4 Air 16GB RAM

**Model Requirements**: See `ml-server/docs/MODEL_REQUIREMENTS.md`
- 17 input features required
- Performance targets: MAE < $0.02, R² > 0.85
- Training data format: CSV with spot price history

**Core Platform Impact**:
- Model upload API must handle new metadata format
- Gap filler service needs AWS EC2 API access for price history
- Model refresh scheduler should be implemented

#### 4. Frontend Changes

**New Component**: `ml-frontend/src/components/FeatureToggles.tsx`
- Material-UI toggle switches for each feature
- Real-time enable/disable
- Displays savings estimates and auto-scan intervals

**Frontend Integration Needed**:
- Add route: `/features` or `/settings/features`
- Add to navigation menu
- Handle API calls to feature toggle endpoints

#### 5. Database Schema Changes (Pending)

**New Tables Needed** (for Core Platform):
```sql
CREATE TABLE feature_scan_history (
    scan_id UUID PRIMARY KEY,
    feature_name VARCHAR(100) NOT NULL,
    scan_time TIMESTAMP NOT NULL,
    findings_count INTEGER,
    total_savings_monthly DECIMAL(10,2),
    execution_time_ms INTEGER,
    status VARCHAR(50)  -- 'completed', 'failed'
);

CREATE TABLE feature_recommendations (
    recommendation_id UUID PRIMARY KEY,
    scan_id UUID REFERENCES feature_scan_history(scan_id),
    feature_name VARCHAR(100) NOT NULL,
    priority VARCHAR(20),
    category VARCHAR(100),
    resource_id VARCHAR(255),
    monthly_cost DECIMAL(10,2),
    savings_monthly DECIMAL(10,2),
    status VARCHAR(50),  -- 'pending', 'executed', 'dismissed'
    created_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP
);
```

### Breaking Changes

**None** - All new features are additive and optional (controlled by feature toggles)

### Migration Steps (for Core Platform)

1. **Update API Routes**:
   ```python
   # Add new decision engine routes
   from decision_engine import (
       IPv4CostTrackerEngine,
       ImageBloatAnalyzerEngine,
       ShadowITTrackerEngine,
       NoisyNeighborDetectorEngine
   )
   
   @router.post("/decision/ipv4-cost-tracking")
   async def ipv4_cost_tracking(request: DecisionRequest):
       engine = IPv4CostTrackerEngine()
       return engine.decide(request.cluster_state, request.requirements)
   ```

2. **Implement Feature Toggle API**:
   ```python
   @router.get("/features/toggles")
   async def get_feature_toggles():
       # Load from ml_config.yaml
       return config.decision_engines.feature_toggles
   
   @router.put("/features/toggles/{feature_name}")
   async def update_feature_toggle(feature_name: str, enabled: bool):
       # Update config and restart services if needed
       pass
   ```

3. **Add Automated Scanning Jobs**:
   ```python
   # Cron jobs or Celery tasks
   @celery.task
   def scan_ipv4_costs():
       if config.feature_toggles.ipv4_cost_tracking.enabled:
           engine = IPv4CostTrackerEngine()
           # Run scan, save results to database
   ```

4. **Update Database Schema**:
   ```bash
   # Run migration
   alembic upgrade head
   ```

5. **Update Frontend**:
   ```typescript
   // Add route in App.tsx
   <Route path="/features" element={<FeatureToggles />} />
   ```

### Testing Checklist

- [ ] Test each new decision engine endpoint
- [ ] Test feature toggle enable/disable
- [ ] Test automated scanning (set interval to 1 minute for testing)
- [ ] Test frontend toggle component
- [ ] Test model training script
- [ ] Test model upload workflow
- [ ] Verify all database migrations
- [ ] Load test decision endpoints (100+ concurrent requests)

### AWS Permissions Required

**New IAM permissions needed** (for Shadow IT Tracker):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeAddresses",
        "elasticloadbalancing:DescribeLoadBalancers",
        "sts:GetCallerIdentity",
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Documentation Updated

1. `ml-server/SESSION_MEMORY.md` - Added comprehensive change log
2. `ml-server/docs/MODEL_REQUIREMENTS.md` - NEW comprehensive guide
3. `ml-server/training/README.md` - NEW training quick start
4. `ml-server/decision_engine/__init__.py` - Updated engine list

### Estimated Integration Effort

- **Core Platform API**: 4-6 hours
- **Database Migration**: 1-2 hours
- **Automated Scanning**: 3-4 hours
- **Frontend Integration**: 2-3 hours
- **Testing**: 3-4 hours
- **Total**: 13-19 hours

### Rollout Plan

**Phase 1** (Week 1):
- Deploy new decision engines (disabled by default)
- Test manually via API

**Phase 2** (Week 2):
- Enable feature toggles in frontend
- Enable one feature at a time (start with IPv4 Tracker)
- Monitor for issues

**Phase 3** (Week 3-4):
- Enable all features
- Implement automated scanning
- Collect user feedback

### Support & Questions

- **Documentation**: See `ml-server/docs/MODEL_REQUIREMENTS.md`
- **Training Issues**: Check `ml-server/training/README.md`
- **API Questions**: Review decision engine source code for input/output schemas

---

**Author**: Claude Code
**Date**: 2025-11-30
**Review Required**: Yes (Core Platform team)
**Deployment Risk**: Low (all features optional, no breaking changes)

