# ML Server - Session Memory & Documentation

## 📋 Overview
**Component**: ML Server (Machine Learning & Decision Engine)
**Purpose**: Handles ML model loading, predictions, and intelligent decision-making for Kubernetes cost optimization
**Instance Type**: Standalone server (can run on separate instance)
**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 🎯 Core Responsibilities

### 1. ML Model Management
- Load and serve trained ML models for:
  - Spot instance interruption prediction
  - Resource utilization forecasting
  - Cost optimization recommendations
- Support model versioning and hot-reloading
- Handle model training data gap filling

### 2. Decision Engine (Pluggable Architecture)
- **Spot Optimizer Engine**: Selects optimal Spot instances based on:
  - Public AWS Spot Advisor data
  - Real-time spot price history
  - Historical interruption patterns
  - Time-of-day risk analysis
- **Bin Packing Engine**: Consolidates workloads to minimize node count
- **Rightsizing Engine**: Matches instance sizes to actual workload requirements
- **Office Hours Scheduler**: Auto-scales dev/staging environments

### 3. Data Processing
- **Gap Filler**: Handles scenario where model trained on old data needs recent data
  - Queries AWS APIs for missing data
  - Fills gaps from last training date to current deployment
  - Supports 15-day lookback requirement

---

## 🔌 Integration Points (Common Components)

### A. Communication with Central Server
**Protocol**: REST API + WebSocket (for real-time updates)
**Endpoints**:
- `POST /api/v1/ml/predict` - Receive prediction requests from Central Server
- `POST /api/v1/ml/decision` - Receive decision engine requests
- `GET /api/v1/ml/health` - Health check endpoint
- `WS /api/v1/ml/stream` - Real-time predictions stream

**Data Flow**:
```
Central Server → ML Server: Request for decision/prediction
ML Server → Central Server: Decision output with recommendations
```

### B. Data Exchange Format (COMMON SCHEMA)
```json
{
  "request_id": "uuid",
  "timestamp": "ISO-8601",
  "cluster_id": "customer-cluster-id",
  "request_type": "spot_selection|bin_packing|rightsizing",
  "input_data": {
    "current_state": {},
    "requirements": {},
    "constraints": {}
  }
}
```

**Response Format**:
```json
{
  "request_id": "uuid",
  "timestamp": "ISO-8601",
  "decision_type": "spot_instance_selection",
  "recommendations": [],
  "confidence_score": 0.85,
  "estimated_savings": 1250.50,
  "risk_assessment": {},
  "execution_plan": []
}
```

### C. Shared Configuration
**Location**: `/config/common.yaml`
**Contains**:
- Central Server connection details
- Database credentials (read-only access)
- AWS IAM role ARN
- Redis cache connection
- Logging configuration

### D. Database Access
**Type**: Read-only access to Central Server database
**Purpose**:
- Fetch historical cluster metrics
- Retrieve customer configuration
- Access training data for model updates

**Tables Used**:
- `clusters` - Cluster metadata
- `spot_history` - Historical spot interruptions
- `metrics_timeseries` - Cluster performance metrics
- `customer_config` - Customer-specific settings

---

## 📁 Directory Structure

```
ml-server/
├── SESSION_MEMORY.md          # This file - session context & updates
├── README.md                   # Setup and deployment instructions
├── requirements.txt            # Python dependencies
├── config/
│   ├── common.yaml            # Shared config with other servers
│   ├── ml_config.yaml         # ML-specific configuration
│   └── models_registry.json   # Model versioning and paths
├── models/
│   ├── spot_predictor.py      # Spot interruption predictor
│   ├── resource_forecaster.py # Resource usage forecasting
│   └── saved/                  # Trained model files
│       ├── spot_predictor_v1.model
│       └── spot_predictor_v1_encoders.pkl
├── decision_engine/
│   ├── base_engine.py         # Base class for all engines
│   ├── spot_optimizer.py      # Spot instance selection engine
│   ├── bin_packing.py         # Workload consolidation engine
│   ├── rightsizing.py         # Instance rightsizing engine
│   └── scheduler.py            # Office hours scheduler
├── data/
│   ├── gap_filler.py          # Fills training data gaps
│   ├── aws_fetcher.py         # Fetches data from AWS APIs
│   └── preprocessor.py        # Data preprocessing utilities
├── api/
│   ├── server.py              # FastAPI server
│   ├── routes/
│   │   ├── predictions.py     # Prediction endpoints
│   │   ├── decisions.py       # Decision engine endpoints
│   │   └── health.py          # Health check endpoints
│   └── middleware/
│       ├── auth.py            # Authentication middleware
│       └── logging.py         # Request logging
├── scripts/
│   ├── install.sh             # Installation script
│   ├── start_server.sh        # Server startup script
│   ├── train_models.sh        # Model training script
│   └── fill_data_gaps.sh      # Data gap filling script
├── tests/
│   ├── test_models.py
│   ├── test_decision_engines.py
│   └── test_api.py
└── docs/
    ├── API_SPEC.md            # API documentation
    └── DECISION_ENGINES.md    # Decision engine algorithms
```

---

## 🔧 Technology Stack

### Core Framework
- **Language**: Python 3.10+
- **API Framework**: FastAPI 0.103+
- **ASGI Server**: Uvicorn

### ML Libraries
- **XGBoost**: 1.7.6 - Spot interruption prediction
- **scikit-learn**: 1.3.0 - Data preprocessing, evaluation
- **TensorFlow**: 2.13.0 - Deep learning models (future)
- **pandas**: 2.0.3 - Data manipulation
- **numpy**: 1.24.3 - Numerical operations

### AWS Integration
- **boto3**: 1.28+ - AWS SDK for Python
- **botocore**: 1.31+ - AWS core library

### Caching & Storage
- **Redis**: 5.0+ - Cache for Spot Advisor data, pricing
- **PostgreSQL**: Read-only client for Central DB

### Monitoring
- **prometheus-client**: Metrics export
- **python-json-logger**: Structured logging

---

## 🚀 Deployment Configuration

### Environment Variables
```bash
# Server Configuration
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001
ML_SERVER_WORKERS=4

# Central Server Connection
CENTRAL_SERVER_URL=http://central-server:8000
CENTRAL_SERVER_API_KEY=xxx

# Database (Read-Only)
DB_HOST=central-db.internal
DB_PORT=5432
DB_NAME=cloudoptim
DB_USER=ml_server_ro
DB_PASSWORD=xxx

# Redis Cache
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_DB=0

# AWS Configuration
AWS_REGION=us-east-1
AWS_ROLE_ARN=arn:aws:iam::xxx:role/MLServerRole

# Model Configuration
MODEL_DIR=/app/models/saved
MODEL_VERSION=v1
AUTO_RELOAD_MODELS=true
```

### Docker Configuration
```yaml
# docker-compose.yml
services:
  ml-server:
    build: ./ml-server
    ports:
      - "8001:8001"
    environment:
      - ML_SERVER_PORT=8001
    volumes:
      - ./ml-server/models/saved:/app/models/saved
      - ./ml-server/config:/app/config
    depends_on:
      - redis
    networks:
      - cloudoptim-network
```

---

## 📊 Key Algorithms & Decision Logic

### 1. Spot Risk Score Calculation
**Formula**:
```
Risk Score = (0.60 × Public_Rate_Score) +
             (0.25 × Volatility_Score) +
             (0.10 × Gap_Score) +
             (0.05 × Time_Score)
```

**Thresholds**:
- Score > 0.65: Safe to use
- Score 0.40-0.65: Use with caution
- Score < 0.40: Avoid

### 2. Diversity Strategy
**Rule**: Never allocate >40% of nodes to single instance family
**Implementation**: `_apply_diversity_strategy()` in spot_optimizer.py

### 3. Data Gap Filling Logic
**Problem**: Model trained on data up to 30 days ago, need 15 days recent data
**Solution**:
1. Identify gap: `last_training_date` to `current_date`
2. Query AWS APIs for missing spot prices
3. Simulate/estimate missing interruption events
4. Merge with existing training data
5. Update model with fresh data

---

## 🔄 Session Updates Log

### 2025-11-28 - Initial Setup
**Changes Made**:
- Created ml-server folder structure
- Implemented base decision engine architecture
- Created SpotOptimizerEngine with risk scoring
- Implemented SpotInterruptionPredictor ML model
- Created DataGapFiller for handling training data gaps
- Defined common integration points with Central Server
- Documented data exchange formats

**Files Created**:
- `decision_engine/base_engine.py`
- `decision_engine/spot_optimizer.py`
- `models/spot_predictor.py`
- `data/gap_filler.py`
- `requirements.txt`

**Next Steps**:
1. Implement remaining decision engines (bin packing, rightsizing)
2. Create FastAPI server with prediction endpoints
3. Add Redis caching for Spot Advisor data
4. Create training pipeline script
5. Add comprehensive tests

---

## 🔗 Common Components Shared Across Servers

### 1. Authentication System
**Location**: Shared library (to be created)
**Used By**: All three servers
**Purpose**: Validate API keys, JWT tokens

### 2. Data Models (Pydantic Schemas)
**Location**: `/common/models.py` (to be created)
**Shared Schemas**:
- `ClusterState`
- `DecisionRequest`
- `DecisionResponse`
- `CustomerConfig`
- `MetricsData`

### 3. Database Schema
**Owner**: Central Server
**Accessed By**: All servers (ML: read-only, Client: read/write via API)
**Key Tables**:
- `customers` - Customer accounts
- `clusters` - Kubernetes clusters
- `nodes` - Cluster nodes
- `spot_events` - Spot interruption events
- `optimization_history` - Decision history

### 4. Message Queue (Future)
**Type**: RabbitMQ or Redis Pub/Sub
**Purpose**: Real-time event streaming between servers
**Events**:
- `spot_interruption_detected`
- `optimization_recommended`
- `cluster_state_changed`

### 5. Configuration Management
**Format**: YAML files
**Structure**:
```yaml
# common.yaml (shared by all servers)
environment: production
log_level: INFO
database:
  host: central-db.internal
  port: 5432
redis:
  host: redis.internal
  port: 6379
```

---

## 📝 API Specifications

### Prediction Endpoint
```http
POST /api/v1/ml/predict/spot-interruption
Content-Type: application/json

{
  "instance_type": "m5.large",
  "region": "us-east-1",
  "availability_zone": "us-east-1a",
  "spot_price": 0.045,
  "launch_time": "2025-11-28T10:00:00Z"
}

Response:
{
  "interruption_probability": 0.08,
  "confidence": 0.92,
  "recommendation": "SAFE_TO_USE"
}
```

### Decision Engine Endpoint
```http
POST /api/v1/ml/decision/spot-optimize
Content-Type: application/json

{
  "cluster_id": "cluster-123",
  "requirements": {
    "cpu_required": 2.0,
    "memory_required": 8.0,
    "node_count": 10,
    "region": "us-east-1"
  }
}

Response:
{
  "decision_type": "spot_instance_selection",
  "recommendations": [...],
  "estimated_savings": 1250.50,
  "execution_plan": [...]
}
```

---

## 🐛 Troubleshooting

### Model Loading Fails
**Symptom**: "Model file not found" error
**Solution**: Check MODEL_DIR path, ensure models are mounted correctly

### Low Prediction Accuracy
**Symptom**: Confidence scores < 0.70
**Solution**: Run data gap filler, retrain model with recent data

### High Response Latency
**Symptom**: API response time > 2 seconds
**Solution**: Enable Redis caching, increase workers, check DB connection

---

## 📌 Important Notes

1. **Pluggable Architecture**: All decision engines inherit from `BaseDecisionEngine`
2. **Fixed Input/Output**: Standard `DecisionInput` and `DecisionOutput` contracts
3. **Agentless**: This server doesn't deploy to customer clusters
4. **Read-Only DB**: ML server has read-only access to Central DB
5. **Model Versioning**: Support multiple model versions, hot-reload capability

---

## 🎯 Integration Checklist

- [ ] Central Server API endpoint configured
- [ ] Database read-only credentials set
- [ ] Redis cache connection tested
- [ ] AWS IAM role configured
- [ ] Common data schemas aligned
- [ ] Authentication middleware implemented
- [ ] Health check endpoint responding
- [ ] Logging forwarding to Central Server
- [ ] Model files deployed and loaded
- [ ] Data gap filler tested

---

**END OF SESSION MEMORY - ML SERVER**
*Append all future changes and updates below this line*

---

## 🔄 Session Updates Log (Continued)

### 2025-11-28 - Architecture Update: Inference-Only ML Server

**CRITICAL ARCHITECTURE CHANGE**: ML Server is now **inference and experimentation only**

#### Key Changes:

**1. No Training on ML Server** ❌
- This server **does NOT train or retrain models**
- All training happens offline / elsewhere:
  - Separate training pipelines
  - Jupyter notebooks
  - Dedicated training infrastructure
- Once trained, models are **exported and uploaded** to this server

**2. Model Upload via Frontend** ✅
- Models and decision engines are **uploaded through ML frontend**
- Use **existing frontend design and layout** (same look & feel as current app)
- Only backend endpoints and wiring change
- Features:
  - Model upload UI (`.pkl` files, serialized models)
  - Decision engine upload/selection
  - Model versioning (A/B testing different versions)
  - Experimentation with new decision engines

**3. Automatic Gap-Filling (October → Today Problem)** 🔧

**The Problem**:
```
Model trained on data up to October
Instance needs predictions using October → current date
Previously required manual data engineering
```

**The Solution** (On ML Server):
1. ML server knows model's `trained_until` date (stored in model metadata)
2. On startup or via ML frontend trigger:
   - Detects gap between `trained_until` and "today"
   - **Directly pulls historic market data on the same server**:
     - Spot/On-Demand prices for all instance types
     - Prices for all regions
     - Required metrics
   - Fills gap with historic prices + feature engineering
3. Once complete:
   - Model immediately produces **up-to-date predictions**
   - No waiting for weeks of new data collection

**Result**: As soon as instance starts/refreshes, get "today-ready" predictions using uploaded model + auto gap-filling

**4. Live Predictions & Decision Streaming** 📊

**Live Predictions**:
- After gap filled, ML server:
  - Continuously runs inference with:
    - Fresh incoming data
    - Up-to-date historic context (already filled)
  - Stores predictions in local store (DB/cache)
  - Optimized for time series plots and quick lookups

**Live Decisions**:
- Decision engine is **pluggable** and uploaded like models
- Fixed input format (normalized metrics, prices, states)
- Fixed output format (actions, scores, explanations)
- ML server:
  - Feeds predictions → decision engine
  - Produces **live, actionable decisions**
  - Examples: "move to Spot in region X", "consolidate nodes", "rightsizing"
  - Exposes via APIs consumed by central backend & dashboards

**5. Frontend Features** (Using Current Design):
- **Keep current frontend design** (layout, styling, UX)
- New functionality:
  - ✅ Model upload UI
  - ✅ Decision engine upload/selection (dropdown for version)
  - ✅ Gap-fill trigger & status display ("Fill missing data from 2025-10-01 to today")
  - ✅ Live charts:
    - Predictions vs actuals (per instance/region)
    - Live decision stream visualized as timelines/markers/event overlays
  - All graphs update in near real-time with same visual style

#### Repository Layout Update

**Folder Structure Change**:
```
/old app/          # Legacy codebase (all existing files)
  ├─ <existing frontend>
  ├─ <existing backend>
  ├─ <Dockerfiles, configs, scripts>
  └─ memory.md (old references)

/new app/          # New architecture
  ├─ ml-server/           # Dedicated ML + decision server
  ├─ core-platform/       # Central backend, DB, admin frontend
  ├─ client-agent/        # Lightweight client-side agent
  ├─ memory.md            # Updated architecture (this approach)
  └─ infra/               # docker-compose, IaC, scripts
```

#### Updated ML Server Responsibilities

**What ML Server DOES**:
- ✅ Host serialized ML models (uploaded, not trained here)
- ✅ Host pluggable decision engine modules
- ✅ Serve model upload endpoints via frontend
- ✅ Automatic gap-filling using historic prices (same server)
- ✅ Run inference continuously
- ✅ Stream live predictions
- ✅ Execute decision engines
- ✅ Expose APIs for predictions & decisions

**What ML Server DOES NOT DO**:
- ❌ Train or retrain models
- ❌ Heavy data engineering
- ❌ Long-term metric storage (that's central platform)

#### New API Endpoints

```http
# Model Management
POST /api/v1/ml/models/upload
  → Upload trained model file
  → Body: multipart/form-data with .pkl file
  → Metadata: model_name, version, trained_until_date

GET /api/v1/ml/models/list
  → List all uploaded models
  → Returns: [{model_id, name, version, trained_until, uploaded_at}]

POST /api/v1/ml/models/activate
  → Set active model version
  → Body: {model_id, version}

# Decision Engine Management
POST /api/v1/ml/engines/upload
  → Upload decision engine module
  → Body: Python module file

GET /api/v1/ml/engines/list
  → List available decision engines

POST /api/v1/ml/engines/select
  → Select active decision engine
  → Body: {engine_id, config}

# Gap Filling
POST /api/v1/ml/gap-filler/analyze
  → Analyze data gaps for active model
  → Returns: {trained_until, current_date, gap_days, required_data_types}

POST /api/v1/ml/gap-filler/fill
  → Trigger automatic gap filling
  → Pulls historic prices from AWS
  → Returns: {status, records_filled, duration}

GET /api/v1/ml/gap-filler/status
  → Check gap-filling progress
  → Returns: {in_progress, percent_complete, eta}
```

#### Updated Environment Variables

```bash
# Model Configuration
MODEL_UPLOAD_DIR=/app/models/uploaded
MODEL_ACTIVE_VERSION=v1
ALLOW_MODEL_TRAINING=false  # Explicitly disabled

# Gap Filling Configuration
GAP_FILLER_ENABLED=true
GAP_FILLER_AWS_REGION=us-east-1
GAP_FILLER_INSTANCE_TYPES=m5.large,m5.xlarge,c5.large
GAP_FILLER_REGIONS=us-east-1,us-west-2,eu-west-1
GAP_FILLER_HISTORIC_DAYS_MAX=90

# Decision Engine Configuration
DECISION_ENGINE_DIR=/app/engines
DECISION_ENGINE_ACTIVE=spot_optimizer_v1
```

#### Migration Plan

**Phase 1** (Current):
- ✅ Documentation updated
- ⏳ Waiting for user approval to implement

**Phase 2** (Implementation):
1. Move existing code to `/old app/`
2. Create `/new app/` structure
3. Implement model upload endpoints
4. Implement gap-filler with AWS price fetching
5. Create ML frontend (reuse current design)
6. Add decision engine upload capability

**Phase 3** (Testing):
1. Test model upload flow
2. Test gap-filling with real AWS data
3. Verify predictions after gap fill
4. Test decision engine swapping

---
