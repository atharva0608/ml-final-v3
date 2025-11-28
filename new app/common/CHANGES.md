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
