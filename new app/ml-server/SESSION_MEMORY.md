# ML Server - Session Memory & Documentation

## 📋 Overview
**Component**: ML Server (Machine Learning & Decision Engine + Backend + Database + Frontend)
**Purpose**: Complete ML infrastructure for agentless Kubernetes cost optimization
**Architecture**: Agentless (No client-side agents, remote K8s API only)
**Components**: FastAPI Backend + PostgreSQL Database + React Frontend + Redis Cache
**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 🎯 Core Responsibilities

### 1. ML Model Management & Inference
- Host pre-trained ML models (uploaded via frontend)
- **Inference-only**: NO training on production server
- Model versioning and hot-reloading
- Support for Spot interruption prediction, resource forecasting

### 2. Decision Engine (Pluggable Architecture)
- **Spot Optimizer Engine**: Select optimal Spot instances using AWS Spot Advisor data (NOT SPS scores)
- **Bin Packing Engine**: Consolidate workloads to minimize node count (Tetris algorithm)
- **Rightsizing Engine**: Match instance sizes to actual workload requirements (deterministic lookup)
- **Office Hours Scheduler**: Auto-scale dev/staging environments
- **Ghost Probe Scanner**: Detect zombie EC2 instances not in K8s clusters
- **Zombie Volume Cleanup**: Identify and remove unattached EBS volumes
- **Network Optimizer**: Cross-AZ traffic affinity optimization
- **OOMKilled Remediation**: Detect and auto-fix OOMKilled pods
- All engines pluggable with fixed input/output contracts

### 3. Pricing Data Management (Backend + Database)
- **PostgreSQL Database**: Store historical Spot prices, On-Demand prices, model metadata
- **Data Fetcher Service**: Automatically fetch AWS pricing data via APIs
- **Gap Filler**: Fill missing data between model training date and current date
- **Data Refresh**: Configurable refresh intervals (hourly, daily)

### 4. ML Backend (FastAPI)
- **Model Upload API**: Upload pre-trained models (.pkl files)
- **Data Gap Filling API**: Analyze and fill data gaps automatically
- **Model Refresh API**: Trigger model refresh with latest pricing data
- **Prediction API**: Real-time predictions and decision recommendations
- **Admin API**: Model management, data management, system health

### 5. ML Frontend (React Dashboard)
- **Model Management UI**: Upload, activate, version models
- **Data Gap Analyzer**: Visual gap detection and filling
- **Pricing Data Viewer**: Browse historical pricing data
- **Model Refresh Dashboard**: Trigger refresh, monitor progress
- **Live Predictions**: Real-time charts for predictions vs actuals
- **Decision Stream**: Visualize live optimization decisions

---

## 🗄️ Database Schema (PostgreSQL)

### Core Tables

```sql
-- Models
CREATE TABLE ml_models (
    model_id UUID PRIMARY KEY,
    model_name VARCHAR(255) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,  -- spot_predictor, resource_forecaster
    trained_until_date DATE NOT NULL,  -- Last date model was trained on
    upload_date TIMESTAMP NOT NULL DEFAULT NOW(),
    uploaded_by VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT FALSE,
    model_file_path TEXT NOT NULL,
    model_metadata JSONB,  -- Feature names, hyperparameters, etc.
    performance_metrics JSONB,  -- Accuracy, precision, recall, etc.
    UNIQUE(model_name, model_version)
);

-- Decision Engines
CREATE TABLE decision_engines (
    engine_id UUID PRIMARY KEY,
    engine_name VARCHAR(255) NOT NULL,
    engine_version VARCHAR(50) NOT NULL,
    engine_type VARCHAR(50) NOT NULL,  -- spot_optimizer, bin_packing, rightsizing
    upload_date TIMESTAMP NOT NULL DEFAULT NOW(),
    active BOOLEAN NOT NULL DEFAULT FALSE,
    engine_file_path TEXT NOT NULL,
    config JSONB,  -- Engine configuration
    input_schema JSONB,  -- Expected input format
    output_schema JSONB,  -- Output format
    UNIQUE(engine_name, engine_version)
);

-- Spot Prices (Historical Data)
CREATE TABLE spot_prices (
    price_id BIGSERIAL PRIMARY KEY,
    instance_type VARCHAR(50) NOT NULL,
    availability_zone VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    spot_price DECIMAL(10,4) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    product_description VARCHAR(100),  -- Linux/UNIX, Windows, etc.
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(instance_type, availability_zone, timestamp)
);

CREATE INDEX idx_spot_prices_lookup ON spot_prices(instance_type, region, timestamp DESC);
CREATE INDEX idx_spot_prices_timestamp ON spot_prices(timestamp DESC);

-- On-Demand Prices
CREATE TABLE on_demand_prices (
    price_id BIGSERIAL PRIMARY KEY,
    instance_type VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    hourly_price DECIMAL(10,4) NOT NULL,
    operating_system VARCHAR(50),  -- Linux, Windows
    effective_date DATE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(instance_type, region, operating_system, effective_date)
);

CREATE INDEX idx_on_demand_prices_lookup ON on_demand_prices(instance_type, region);

-- Spot Advisor Data (Public AWS Data)
CREATE TABLE spot_advisor_data (
    advisor_id BIGSERIAL PRIMARY KEY,
    instance_type VARCHAR(50) NOT NULL,
    region VARCHAR(50) NOT NULL,
    interruption_rate VARCHAR(50) NOT NULL,  -- <5%, 5-10%, 10-15%, 15-20%, >20%
    savings_over_od INTEGER,  -- Percentage savings over On-Demand
    last_updated TIMESTAMP NOT NULL,
    raw_data JSONB,  -- Full AWS Spot Advisor JSON
    UNIQUE(instance_type, region)
);

CREATE INDEX idx_spot_advisor_lookup ON spot_advisor_data(instance_type, region);

-- Data Gap Analysis
CREATE TABLE data_gaps (
    gap_id UUID PRIMARY KEY,
    model_id UUID REFERENCES ml_models(model_id),
    gap_start_date DATE NOT NULL,
    gap_end_date DATE NOT NULL,
    gap_days INTEGER NOT NULL,
    data_type VARCHAR(50) NOT NULL,  -- spot_prices, on_demand_prices
    regions TEXT[],
    instance_types TEXT[],
    status VARCHAR(50) NOT NULL,  -- pending, filling, completed, failed
    records_filled INTEGER DEFAULT 0,
    records_expected INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Model Refresh History
CREATE TABLE model_refresh_history (
    refresh_id UUID PRIMARY KEY,
    model_id UUID REFERENCES ml_models(model_id),
    refresh_type VARCHAR(50) NOT NULL,  -- manual, scheduled, auto
    data_fetched_from DATE,
    data_fetched_to DATE,
    records_fetched INTEGER,
    status VARCHAR(50) NOT NULL,  -- in_progress, completed, failed
    triggered_by VARCHAR(255),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    error_message TEXT
);

-- Predictions Log (for monitoring and comparison)
CREATE TABLE predictions_log (
    prediction_id BIGSERIAL PRIMARY KEY,
    model_id UUID REFERENCES ml_models(model_id),
    prediction_type VARCHAR(50) NOT NULL,  -- spot_interruption, cost_forecast
    input_data JSONB NOT NULL,
    prediction_output JSONB NOT NULL,
    confidence_score DECIMAL(5,4),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_predictions_log_model ON predictions_log(model_id, created_at DESC);
CREATE INDEX idx_predictions_log_timestamp ON predictions_log(created_at DESC);

-- Decision Execution Log
CREATE TABLE decision_execution_log (
    execution_id UUID PRIMARY KEY,
    engine_id UUID REFERENCES decision_engines(engine_id),
    decision_type VARCHAR(50) NOT NULL,  -- spot_optimize, bin_pack, rightsize
    cluster_id VARCHAR(255),
    input_state JSONB NOT NULL,
    recommendations JSONB NOT NULL,
    confidence_score DECIMAL(5,4),
    estimated_savings DECIMAL(10,2),
    executed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_decision_log_engine ON decision_execution_log(engine_id, executed_at DESC);
CREATE INDEX idx_decision_log_cluster ON decision_execution_log(cluster_id, executed_at DESC);
```

---

## 🔌 Integration Points (Agentless Architecture)

### A. Communication with Core Platform
**Protocol**: REST API + WebSocket (for real-time updates)
**Direction**: Core Platform → ML Server (request/response)
**Endpoints**:
- `POST /api/v1/ml/predict` - Receive prediction requests from Core Platform
- `POST /api/v1/ml/decision` - Receive decision engine requests
- `GET /api/v1/ml/health` - Health check endpoint
- `WS /api/v1/ml/stream` - Real-time predictions stream

**Data Flow**:
```
Core Platform → ML Server: Request for decision/prediction
ML Server: Query database for pricing data
ML Server: Run model inference
ML Server → Core Platform: Decision output with recommendations
ML Server: No direct interaction with customer clusters (agentless)
```

**Note**: ML Server does NOT interact with customer clusters directly. All cluster operations are handled by Core Platform via remote Kubernetes API.

### B. AWS API Integration (Data Fetching)
**Purpose**: Fetch pricing data to populate database

**APIs Used**:
- `DescribeSpotPriceHistory` - Historical Spot prices
- AWS Spot Advisor JSON - Public interruption rates
- AWS Pricing API - On-Demand pricing

**Data Flow**:
```
ML Server Backend → AWS EC2 API: DescribeSpotPriceHistory
AWS → ML Server: Spot price records
ML Server → Database: Store pricing data
ML Server → Redis: Cache recent data
```

### C. Redis Cache
**Purpose**: High-speed cache for frequently accessed data
**Cached Data**:
- AWS Spot Advisor data (refresh every 1 hour)
- Recent Spot prices (last 7 days)
- Active model metadata
- Recent predictions

---

## 📁 Directory Structure

```
ml-server/
├── SESSION_MEMORY.md          # This file - session context & updates
├── README.md                   # Setup and deployment instructions
├── requirements.txt            # Python dependencies
├── config/
│   ├── common.yaml            # Shared config with Core Platform
│   ├── ml_config.yaml         # ML-specific configuration
│   ├── database.yaml          # Database configuration
│   └── models_registry.json   # Model versioning and paths
├── backend/
│   ├── main.py                # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── models.py      # Model management endpoints
│   │   │   ├── engines.py     # Decision engine endpoints
│   │   │   ├── predictions.py # Prediction endpoints
│   │   │   ├── gap_filler.py  # Data gap filling endpoints
│   │   │   ├── pricing.py     # Pricing data endpoints
│   │   │   ├── refresh.py     # Model refresh endpoints
│   │   │   └── health.py      # Health check endpoints
│   │   └── middleware/
│   │       ├── auth.py        # Authentication middleware
│   │       └── logging.py     # Request logging
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   ├── schemas.py         # Pydantic schemas
│   │   ├── migrations/        # Alembic migrations
│   │   └── connection.py      # Database connection pool
│   ├── services/
│   │   ├── __init__.py
│   │   ├── model_service.py   # Model management logic
│   │   ├── engine_service.py  # Decision engine logic
│   │   ├── pricing_service.py # Pricing data fetching
│   │   ├── gap_filler_service.py  # Gap filling logic
│   │   ├── refresh_service.py # Model refresh logic
│   │   ├── aws_fetcher.py     # AWS API data fetcher
│   │   └── cache_service.py   # Redis cache management
│   └── utils/
│       ├── __init__.py
│       ├── validators.py      # Input validation
│       └── helpers.py         # Helper functions
├── models/
│   ├── __init__.py
│   ├── spot_predictor.py      # Spot interruption predictor
│   ├── resource_forecaster.py # Resource usage forecasting
│   ├── loader.py              # Model loading utilities
│   └── uploaded/              # Uploaded model files (.pkl)
├── decision_engine/
│   ├── __init__.py
│   ├── base_engine.py         # Base class for all engines
│   ├── spot_optimizer.py      # Spot instance selection (AWS Spot Advisor, NO SPS)
│   ├── bin_packing.py         # Workload consolidation (Tetris algorithm)
│   ├── rightsizing.py         # Instance rightsizing (deterministic lookup)
│   ├── scheduler.py           # Office hours scheduler
│   ├── ghost_probe.py         # Zombie EC2 instance scanner
│   ├── volume_cleanup.py      # Zombie volume cleanup
│   ├── network_optimizer.py   # Cross-AZ traffic optimization
│   ├── oomkilled_remediation.py  # OOMKilled pod auto-fix
│   └── uploaded/              # Uploaded engine files (.py)
├── ml-frontend/               # React frontend
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── public/
│   ├── src/
│   │   ├── index.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── ModelManagement/
│   │   │   │   ├── ModelUpload.tsx
│   │   │   │   ├── ModelList.tsx
│   │   │   │   ├── ModelDetails.tsx
│   │   │   │   └── ModelActivation.tsx
│   │   │   ├── DataGapFiller/
│   │   │   │   ├── GapAnalyzer.tsx
│   │   │   │   ├── GapFillerTrigger.tsx
│   │   │   │   ├── GapFillerStatus.tsx
│   │   │   │   └── GapHistory.tsx
│   │   │   ├── PricingData/
│   │   │   │   ├── SpotPriceViewer.tsx
│   │   │   │   ├── OnDemandPriceViewer.tsx
│   │   │   │   ├── SpotAdvisorViewer.tsx
│   │   │   │   └── PriceCharts.tsx
│   │   │   ├── ModelRefresh/
│   │   │   │   ├── RefreshTrigger.tsx
│   │   │   │   ├── RefreshStatus.tsx
│   │   │   │   ├── RefreshHistory.tsx
│   │   │   │   └── AutoRefreshSchedule.tsx
│   │   │   ├── LivePredictions/
│   │   │   │   ├── PredictionChart.tsx
│   │   │   │   ├── PredictionVsActual.tsx
│   │   │   │   └── ConfidenceMetrics.tsx
│   │   │   ├── DecisionEngines/
│   │   │   │   ├── EngineUpload.tsx
│   │   │   │   ├── EngineList.tsx
│   │   │   │   ├── EngineConfig.tsx
│   │   │   │   └── DecisionStream.tsx
│   │   │   └── Dashboard/
│   │   │       ├── Overview.tsx
│   │   │       ├── SystemHealth.tsx
│   │   │       └── Metrics.tsx
│   │   ├── services/
│   │   │   └── api.ts         # API client
│   │   ├── types/
│   │   │   └── index.ts       # TypeScript types
│   │   └── utils/
│   │       └── helpers.ts     # Helper functions
│   └── .env.example
├── scripts/
│   ├── install.sh             # Installation script
│   ├── setup_database.sh      # Database setup
│   ├── start_backend.sh       # Backend startup
│   ├── start_frontend.sh      # Frontend startup
│   ├── fetch_spot_advisor.sh  # Fetch AWS Spot Advisor data
│   └── migrate_database.sh    # Run database migrations
├── tests/
│   ├── test_models.py
│   ├── test_decision_engines.py
│   ├── test_api.py
│   ├── test_gap_filler.py
│   └── test_pricing_service.py
└── docs/
    ├── API_SPEC.md            # API documentation
    ├── DATABASE_SCHEMA.md     # Database schema documentation
    ├── DECISION_ENGINES.md    # Decision engine algorithms
    └── FRONTEND_GUIDE.md      # Frontend usage guide
```

---

## 🚀 API Endpoints (Complete Specification)

### Model Management

```http
POST /api/v1/ml/models/upload
  → Upload pre-trained model
  → Body: multipart/form-data
    - file: .pkl file
    - model_name: string
    - model_version: string
    - model_type: string (spot_predictor, resource_forecaster)
    - trained_until_date: YYYY-MM-DD
    - metadata: JSON (optional)
  → Returns: {model_id, status, upload_path}

GET /api/v1/ml/models/list
  → List all uploaded models
  → Query params: ?active=true|false, ?limit=50, ?offset=0
  → Returns: [{model_id, name, version, trained_until, active, uploaded_at}]

POST /api/v1/ml/models/activate
  → Activate model version
  → Body: {model_id, version}
  → Returns: {status, activated_at, previous_active}

DELETE /api/v1/ml/models/{model_id}
  → Delete a model version
  → Returns: {status, deleted_at}

GET /api/v1/ml/models/{model_id}/details
  → Get model details
  → Returns: {model_id, metadata, performance_metrics, usage_stats}

GET /api/v1/ml/models/{model_id}/performance
  → Get model performance metrics
  → Returns: {accuracy, precision, recall, f1_score, predictions_count}
```

### Decision Engine Management

```http
POST /api/v1/ml/engines/upload
  → Upload decision engine module
  → Body: multipart/form-data
    - file: .py file
    - engine_name: string
    - engine_version: string
    - engine_type: string (spot_optimizer, bin_packing, rightsizing, scheduler, ghost_probe, volume_cleanup, network_optimizer, oomkilled_remediation)
    - config: JSON (optional)
  → Returns: {engine_id, status}

GET /api/v1/ml/engines/list
  → List available decision engines
  → Returns: [{engine_id, name, version, type, active}]

POST /api/v1/ml/engines/select
  → Select active decision engine
  → Body: {engine_id, config}
  → Returns: {status, activated_at}

GET /api/v1/ml/engines/{engine_id}/metadata
  → Get engine metadata
  → Returns: {engine_id, input_schema, output_schema, config}
```

### Data Gap Filling

```http
POST /api/v1/ml/gap-filler/analyze
  → Analyze data gaps for active model
  → Body: {model_id, required_lookback_days: 15}
  → Returns: {
      trained_until: "2025-10-31",
      current_date: "2025-11-28",
      gap_days: 28,
      required_data_types: ["spot_prices", "on_demand_prices"],
      estimated_records: 150000
    }

POST /api/v1/ml/gap-filler/fill
  → Trigger automatic gap filling
  → Body: {
      model_id,
      instance_types: ["m5.large", "c5.large", ...],
      regions: ["us-east-1", "us-west-2"],
      gap_start_date: "2025-10-31",
      gap_end_date: "2025-11-28"
    }
  → Returns: {
      gap_id,
      status: "filling",
      estimated_duration_minutes: 5
    }

GET /api/v1/ml/gap-filler/status/{gap_id}
  → Check gap-filling progress
  → Returns: {
      gap_id,
      status: "filling|completed|failed",
      percent_complete: 75,
      records_filled: 112500,
      records_expected: 150000,
      eta_seconds: 30,
      started_at,
      error_message: null
    }

GET /api/v1/ml/gap-filler/history
  → Get gap-filling history
  → Query params: ?limit=20, ?offset=0
  → Returns: [{gap_id, model_id, gap_days, status, completed_at}]
```

### Model Refresh

```http
POST /api/v1/ml/refresh/trigger
  → Trigger model refresh with latest data
  → Body: {
      model_id,
      refresh_from_date: "2025-11-21",  # Fetch data from this date
      refresh_to_date: "2025-11-28",    # Fetch data until this date
      instance_types: ["m5.*", "c5.*"],  # Pattern matching supported
      regions: ["us-east-1", "us-west-2", "eu-west-1"],
      auto_activate: true  # Activate after refresh
    }
  → Returns: {
      refresh_id,
      status: "in_progress",
      estimated_duration_minutes: 3
    }

GET /api/v1/ml/refresh/status/{refresh_id}
  → Check refresh progress
  → Returns: {
      refresh_id,
      status: "in_progress|completed|failed",
      percent_complete: 60,
      records_fetched: 90000,
      started_at,
      eta_seconds: 45,
      error_message: null
    }

GET /api/v1/ml/refresh/history
  → Get refresh history
  → Query params: ?model_id, ?limit=20, ?offset=0
  → Returns: [{refresh_id, model_id, records_fetched, duration_seconds, completed_at}]

POST /api/v1/ml/refresh/schedule
  → Schedule automatic refresh
  → Body: {
      model_id,
      schedule_type: "daily|weekly",
      time: "02:00",  # UTC time
      lookback_days: 7,  # Fetch last 7 days on each refresh
      enabled: true
    }
  → Returns: {schedule_id, next_run_at}
```

### Pricing Data

```http
GET /api/v1/ml/pricing/spot
  → Get Spot price history
  → Query params:
      ?instance_type=m5.large
      &region=us-east-1
      &start_date=2025-11-01
      &end_date=2025-11-28
      &limit=1000
  → Returns: [{instance_type, az, region, spot_price, timestamp}]

GET /api/v1/ml/pricing/on-demand
  → Get On-Demand prices
  → Query params: ?instance_type, ?region
  → Returns: [{instance_type, region, hourly_price, effective_date}]

GET /api/v1/ml/pricing/spot-advisor
  → Get AWS Spot Advisor data
  → Query params: ?instance_type, ?region
  → Returns: [{instance_type, region, interruption_rate, savings_over_od}]

POST /api/v1/ml/pricing/fetch
  → Manually fetch pricing data
  → Body: {
      data_type: "spot_prices|on_demand_prices|spot_advisor",
      instance_types: ["m5.large", "c5.large"],
      regions: ["us-east-1"],
      start_date: "2025-11-01",
      end_date: "2025-11-28"
    }
  → Returns: {task_id, status, estimated_records}

GET /api/v1/ml/pricing/stats
  → Get pricing data statistics
  → Returns: {
      spot_prices_count,
      on_demand_prices_count,
      spot_advisor_count,
      last_updated,
      coverage: {
        instance_types: 150,
        regions: 5,
        date_range: {oldest: "2025-10-01", newest: "2025-11-28"}
      }
    }
```

### Predictions & Decisions

```http
POST /api/v1/ml/predict/spot-interruption
  → Get Spot interruption prediction
  → Body: {instance_type, region, az, spot_price, launch_time}
  → Returns: {interruption_probability, confidence, recommendation}

POST /api/v1/ml/decision/spot-optimize
  → Get Spot optimization decision
  → Body: DecisionRequest (see common schemas)
  → Returns: DecisionResponse with recommendations

GET /api/v1/ml/predictions/live
  → Stream live predictions (WebSocket)
  → Returns: Real-time prediction stream

GET /api/v1/ml/predictions/history
  → Get prediction history
  → Query params: ?model_id, ?limit=100, ?offset=0
  → Returns: [{prediction_id, prediction_type, confidence, created_at}]

GET /api/v1/ml/decisions/history
  → Get decision execution history
  → Query params: ?engine_id, ?cluster_id, ?limit=50
  → Returns: [{execution_id, decision_type, estimated_savings, executed_at}]
```

### System Health

```http
GET /api/v1/ml/health
  → Health check
  → Returns: {status: "healthy", database: "up", redis: "up", models_loaded: 2}

GET /api/v1/ml/metrics
  → Get system metrics
  → Returns: {
      predictions_per_minute,
      decisions_per_minute,
      avg_prediction_latency_ms,
      cache_hit_rate,
      database_connections
    }
```

---

## 🖥️ Frontend Features (ML Dashboard)

### 1. Model Management Page

**Model Upload**:
- Drag-and-drop file upload (.pkl files)
- Form fields: model name, version, type, trained_until date
- Upload progress bar with percentage
- Validation: file size, format, metadata

**Model List**:
- Table view: name, version, type, trained_until, status (active/inactive), uploaded_at
- Actions: Activate, Delete, View Details, Download
- Filters: active/inactive, model type, date range
- Sorting: by name, upload date, usage count

**Model Details**:
- Metadata display: feature names, hyperparameters, training date
- Performance metrics: accuracy, precision, recall, F1 score
- Usage statistics: prediction count, average latency
- Version history

### 2. Data Gap Filler Page

**Gap Analyzer**:
- Visual timeline: training date → current date with gap highlighted
- Gap summary: gap in days, missing data types
- Instance type selector (multi-select)
- Region selector (multi-select)
- "Analyze Gap" button → shows estimated records to fetch

**Fill Gap UI**:
- Configuration form:
  - Date range picker (gap start → gap end)
  - Instance type multi-select (with "Select All m5.*" pattern matching)
  - Region multi-select
  - Priority: Normal | High
- "Fill Gap" button
- Real-time progress:
  - Progress bar (0-100%)
  - Records filled: 112,500 / 150,000
  - ETA: 30 seconds
  - Live log stream

**Gap History**:
- Table: gap_id, model, gap range, records filled, status, completed_at
- Filter by status, model, date range

### 3. Pricing Data Viewer

**Spot Price Explorer**:
- Chart: Spot price over time (line chart)
- Filters: instance type, region, AZ, date range
- Table view with pagination
- Export to CSV

**On-Demand Price Viewer**:
- Current On-Demand prices by instance type and region
- Comparison: Spot vs On-Demand savings percentage
- Price trend charts

**Spot Advisor Viewer**:
- Heatmap: instance types × regions with interruption rate colors
  - Green: <5%
  - Yellow: 5-15%
  - Red: >15%
- Savings over On-Demand percentage

### 4. Model Refresh Dashboard

**Refresh Trigger**:
- Form fields:
  - Select model (dropdown)
  - Date range: "Fetch data from [date] to [date]"
  - Instance types (pattern matching: "m5.*", "c5.*")
  - Regions (multi-select)
  - Auto-activate model after refresh (checkbox)
- "Trigger Refresh" button
- Estimated duration display

**Refresh Progress**:
- Live status:
  - Status: In Progress / Completed / Failed
  - Progress bar: 60%
  - Records fetched: 90,000
  - ETA: 45 seconds
- Logs panel (scrollable, auto-updates)

**Refresh History**:
- Table: refresh_id, model, date range, records fetched, duration, status, completed_at
- Filter by model, status, date range

**Auto-Refresh Schedule**:
- Configure automatic refresh:
  - Schedule type: Daily / Weekly
  - Time: 02:00 UTC
  - Lookback days: 7 (fetch last 7 days)
  - Enable/Disable toggle
- Next scheduled run display

### 5. Live Predictions Dashboard

**Prediction Charts**:
- Real-time line chart: Predictions over time
- Prediction vs Actual comparison (when actuals available)
- Confidence score distribution histogram
- Predictions per minute counter

**Prediction Stream**:
- Live table of recent predictions (auto-updates)
- Columns: timestamp, prediction type, input, output, confidence
- Color coding by confidence level (high=green, low=red)

**Performance Metrics**:
- Model accuracy: 94.2%
- Avg prediction latency: 45ms
- Predictions today: 15,234
- Drift detection alerts (if model accuracy drops)

### 6. Decision Engine Dashboard

**Engine Upload**:
- Upload Python module (.py file)
- Form: engine name, version, type, config JSON
- Schema validator: validates input/output schemas

**Engine List & Config**:
- Table: engine name, version, type, status (active/inactive)
- Config editor (JSON editor with validation)
- Test engine with sample data

**Decision Stream**:
- Live decisions feed (WebSocket)
- Timeline view with decision markers
- Click decision → expand details (recommendations, execution plan, savings)
- Filter by decision type, cluster

---

## 🔧 Technology Stack

### Backend
- **Language**: Python 3.10+
- **API Framework**: FastAPI 0.103+
- **ASGI Server**: Uvicorn
- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Validation**: Pydantic 2.0+

### Database & Caching
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Connection Pooling**: asyncpg

### ML Libraries
- **XGBoost**: 1.7.6 - Spot interruption prediction
- **scikit-learn**: 1.3.0 - Data preprocessing, evaluation
- **pandas**: 2.0.3 - Data manipulation
- **numpy**: 1.24.3 - Numerical operations

### AWS Integration
- **boto3**: 1.28+ - AWS SDK for Python
- **APIs**: EC2 (DescribeSpotPriceHistory), Pricing API, Spot Advisor JSON

### Frontend
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit
- **UI Library**: Material-UI (MUI)
- **Charts**: Recharts for data visualization
- **HTTP Client**: Axios
- **WebSocket**: socket.io-client (for live streams)

### Monitoring & Logging
- **prometheus-client**: Metrics export
- **python-json-logger**: Structured logging
- **Sentry**: Error tracking (optional)

---

## 📦 Installation & Setup

### System Requirements

**Operating System**:
- Ubuntu 22.04 LTS or 24.04 LTS (recommended)
- Amazon Linux 2023
- Other Linux distributions (with adjustments)

**Hardware Minimum**:
- CPU: 4 cores (8 cores recommended for production)
- RAM: 8GB (16GB recommended for production)
- Disk: 50GB SSD (100GB+ for production with pricing data)

**Software Prerequisites**:
- Python 3.10+ (3.11 recommended)
- PostgreSQL 15+
- Redis 7+
- Node.js 20.x LTS (for frontend)
- Docker (optional, for containerized deployment)
- AWS CLI v2 (for Spot Advisor data fetching)

---

### Installation Script

**Automated Setup** (Ubuntu 22.04/24.04):

```bash
#!/bin/bash
# ML Server Installation Script
# Based on old app/old-version/central-server/scripts/setup.sh

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

log "Starting ML Server Installation..."

# Update system
log "Step 1: Updating system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install system dependencies
log "Step 2: Installing system dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql-15 \
    postgresql-contrib \
    redis-server \
    nginx \
    curl \
    wget \
    git \
    build-essential \
    libpq-dev \
    unzip

log "System dependencies installed"

# Install Node.js 20.x LTS (for frontend)
log "Step 3: Installing Node.js 20.x LTS..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi
log "Node.js $(node --version) installed"

# Install AWS CLI v2
log "Step 4: Installing AWS CLI v2..."
if ! command -v aws &> /dev/null; then
    cd /tmp
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install > /dev/null 2>&1
    rm -rf aws awscliv2.zip
fi
log "AWS CLI $(aws --version 2>&1 | cut -d' ' -f1) installed"

# Create directory structure
log "Step 5: Creating directory structure..."
APP_DIR="/opt/ml-server"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

mkdir -p $APP_DIR/backend
mkdir -p $APP_DIR/models/uploaded
mkdir -p $APP_DIR/decision_engine/uploaded
mkdir -p $APP_DIR/ml-frontend
mkdir -p $APP_DIR/scripts
mkdir -p /var/log/ml-server

log "Directory structure created"

# Setup Python virtual environment
log "Step 6: Setting up Python virtual environment..."
cd $APP_DIR/backend
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
log "Step 7: Installing Python dependencies..."
cat > requirements.txt << 'EOF'
# Core ML Libraries (from old app/ml-component/requirements.txt)
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
xgboost==1.7.6
lightgbm==4.0.0

# API Framework
fastapi==0.103.0
uvicorn[standard]==0.23.2
pydantic==2.3.0
pydantic-settings==2.0.3

# Database
asyncpg==0.29.0
sqlalchemy==2.0.21
alembic==1.12.0

# Redis
redis==5.0.0
hiredis==2.2.3

# AWS Integration
boto3==1.28.25
botocore==1.31.25

# Monitoring
prometheus-client==0.17.1
python-json-logger==2.0.7

# HTTP Client
httpx==0.24.1
requests==2.31.0

# Environment
python-dotenv==1.0.0

# Testing
pytest==7.4.0
pytest-asyncio==0.21.1
pytest-cov==4.1.0
EOF

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

log "Python dependencies installed"
deactivate

# Setup PostgreSQL database
log "Step 8: Configuring PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << PSQL_EOF
CREATE DATABASE ml_server;
CREATE USER ml_server WITH ENCRYPTED PASSWORD 'ml_server_password';
GRANT ALL PRIVILEGES ON DATABASE ml_server TO ml_server;
\c ml_server
GRANT ALL ON SCHEMA public TO ml_server;
PSQL_EOF

log "PostgreSQL database created"

# Setup Redis
log "Step 9: Configuring Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Update Redis configuration for production
sudo tee -a /etc/redis/redis.conf > /dev/null << 'REDIS_EOF'
maxmemory 2gb
maxmemory-policy allkeys-lru
REDIS_EOF

sudo systemctl restart redis-server
log "Redis configured"

# Create environment configuration
log "Step 10: Creating environment configuration..."
cat > $APP_DIR/backend/.env << 'ENV_EOF'
# ML Server Configuration
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001
ML_SERVER_WORKERS=4

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ml_server
DB_USER=ml_server
DB_PASSWORD=ml_server_password
DB_POOL_SIZE=10

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_TTL=3600

# AWS (for Spot Advisor data fetching)
AWS_REGION=us-east-1
SPOT_ADVISOR_URL=https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json

# Models
MODEL_UPLOAD_DIR=/opt/ml-server/models/uploaded
DECISION_ENGINE_DIR=/opt/ml-server/decision_engine/uploaded
MAX_MODEL_FILE_SIZE_MB=500

# Gap Filler
GAP_FILLER_ENABLED=true
GAP_FILLER_DEFAULT_LOOKBACK_DAYS=15

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
ENV_EOF

log "Environment configuration created"

# Create systemd service
log "Step 11: Creating systemd service..."
sudo tee /etc/systemd/system/ml-server-backend.service > /dev/null << SERVICE_EOF
[Unit]
Description=ML Server Backend (FastAPI)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/backend/.env
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=10
StandardOutput=append:/var/log/ml-server/backend.log
StandardError=append:/var/log/ml-server/backend-error.log

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl enable ml-server-backend

log "Systemd service created"

# Setup frontend
log "Step 12: Setting up React frontend..."
cd $APP_DIR/ml-frontend

# Install frontend dependencies
npm install

# Build frontend
npm run build

# Configure Nginx
sudo tee /etc/nginx/sites-available/ml-server << 'NGINX_EOF'
server {
    listen 3001 default_server;
    server_name _;

    root /opt/ml-server/ml-frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
NGINX_EOF

sudo ln -sf /etc/nginx/sites-available/ml-server /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

log "Frontend configured"

# Create helper scripts
log "Step 13: Creating helper scripts..."

# Start script
cat > $APP_DIR/scripts/start.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "Starting ML Server..."
sudo systemctl start ml-server-backend
sudo systemctl start nginx
echo "ML Server started!"
SCRIPT_EOF
chmod +x $APP_DIR/scripts/start.sh

# Stop script
cat > $APP_DIR/scripts/stop.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "Stopping ML Server..."
sudo systemctl stop ml-server-backend
echo "ML Server stopped!"
SCRIPT_EOF
chmod +x $APP_DIR/scripts/stop.sh

# Status script
cat > $APP_DIR/scripts/status.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "=== ML Server Status ==="
sudo systemctl status ml-server-backend --no-pager
echo ""
echo "=== Health Check ==="
curl -s http://localhost:8001/api/v1/ml/health | jq .
SCRIPT_EOF
chmod +x $APP_DIR/scripts/status.sh

# Fetch Spot Advisor data script
cat > $APP_DIR/scripts/fetch_spot_advisor.sh << 'SCRIPT_EOF'
#!/bin/bash
echo "Fetching AWS Spot Advisor data..."
curl -s https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json \
    | jq . > /tmp/spot-advisor-data.json
echo "Spot Advisor data saved to /tmp/spot-advisor-data.json"
SCRIPT_EOF
chmod +x $APP_DIR/scripts/fetch_spot_advisor.sh

log "Helper scripts created"

# Installation complete
log "============================================"
log "ML Server Installation Complete!"
log "============================================"
log ""
log "✓ Backend: FastAPI on port 8001"
log "✓ Frontend: React on port 3001"
log "✓ Database: PostgreSQL (ml_server)"
log "✓ Cache: Redis"
log ""
log "Quick Commands:"
log "  Start:  $APP_DIR/scripts/start.sh"
log "  Stop:   $APP_DIR/scripts/stop.sh"
log "  Status: $APP_DIR/scripts/status.sh"
log ""
log "Backend API: http://localhost:8001/api/v1/ml/"
log "Frontend UI: http://localhost:3001"
log "Health Check: http://localhost:8001/api/v1/ml/health"
log "============================================"
```

**Save as**: `install_ml_server.sh`

**Run**:
```bash
chmod +x install_ml_server.sh
./install_ml_server.sh
```

---

### Manual Installation Steps

For manual installation or troubleshooting, follow these steps:

#### 1. Install System Dependencies

```bash
# Ubuntu 22.04/24.04
sudo apt-get update
sudo apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    postgresql-15 postgresql-contrib \
    redis-server \
    nginx \
    curl wget git unzip \
    build-essential libpq-dev

# Node.js 20.x LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# AWS CLI v2
cd /tmp
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
sudo ./aws/install
```

#### 2. Setup Python Environment

```bash
# Create virtual environment
python3.11 -m venv /opt/ml-server/backend/venv
source /opt/ml-server/backend/venv/bin/activate

# Install dependencies (see requirements.txt above)
pip install -r requirements.txt
```

#### 3. Setup Database

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Create database
sudo -u postgres psql << EOF
CREATE DATABASE ml_server;
CREATE USER ml_server WITH ENCRYPTED PASSWORD 'ml_server_password';
GRANT ALL PRIVILEGES ON DATABASE ml_server TO ml_server;
\c ml_server
GRANT ALL ON SCHEMA public TO ml_server;
EOF

# Run migrations
cd /opt/ml-server/backend
alembic upgrade head
```

#### 4. Setup Redis

```bash
# Start Redis
sudo systemctl start redis-server

# Configure for production
echo "maxmemory 2gb" | sudo tee -a /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" | sudo tee -a /etc/redis/redis.conf
sudo systemctl restart redis-server
```

#### 5. Configure Environment

Create `/opt/ml-server/backend/.env` (see environment variables section below)

#### 6. Start Services

```bash
# Start backend
sudo systemctl start ml-server-backend

# Build and serve frontend
cd /opt/ml-server/ml-frontend
npm install
npm run build
sudo systemctl start nginx
```

---

### Version Reference (from old setup scripts)

**Python Packages**:
```txt
# ML Libraries
numpy==1.24.3
pandas==2.0.3
scikit-learn==1.3.0
xgboost==1.7.6
lightgbm==4.0.0

# API Framework
fastapi==0.103.0
uvicorn==0.23.2
pydantic==2.3.0

# Database
asyncpg==0.29.0
sqlalchemy==2.0.21
alembic==1.12.0

# AWS
boto3==1.28.25

# Redis
redis==5.0.0
```

**System Packages**:
- Python: 3.10+ (3.11 recommended)
- PostgreSQL: 15+
- Redis: 7+
- Node.js: 20.x LTS
- Nginx: 1.18+

---

### Verification

After installation, verify everything is working:

```bash
# Check services
sudo systemctl status ml-server-backend
sudo systemctl status postgresql
sudo systemctl status redis-server
sudo systemctl status nginx

# Test backend API
curl http://localhost:8001/api/v1/ml/health

# Test database connection
psql -h localhost -U ml_server -d ml_server -c "SELECT 1;"

# Test Redis
redis-cli ping

# Fetch Spot Advisor data
curl -s https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json | jq . | head -20
```

---

## 🚀 Deployment Configuration

### Environment Variables

```bash
# Server Configuration
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001
ML_SERVER_WORKERS=4
FRONTEND_PORT=3001

# Database
DB_HOST=postgres-ml.internal
DB_PORT=5432
DB_NAME=ml_server
DB_USER=ml_server
DB_PASSWORD=xxx
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# Redis Cache
REDIS_HOST=redis-ml.internal
REDIS_PORT=6379
REDIS_DB=0
REDIS_CACHE_TTL=3600  # 1 hour cache for Spot Advisor
REDIS_POOL_SIZE=10

# Core Platform Connection
CORE_PLATFORM_URL=http://core-platform:8000
CORE_PLATFORM_API_KEY=xxx

# AWS Configuration (for data fetching only, no cluster access)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=xxx  # For pricing data fetch
AWS_SECRET_ACCESS_KEY=xxx
SPOT_ADVISOR_URL=https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json

# Model Configuration
MODEL_UPLOAD_DIR=/app/models/uploaded
MODEL_ACTIVE_VERSION=v1
ALLOW_MODEL_TRAINING=false  # Explicitly disabled (inference-only)
AUTO_RELOAD_MODELS=true
MAX_MODEL_FILE_SIZE_MB=500

# Gap Filler Configuration
GAP_FILLER_ENABLED=true
GAP_FILLER_DEFAULT_LOOKBACK_DAYS=15
GAP_FILLER_MAX_LOOKBACK_DAYS=90
GAP_FILLER_BATCH_SIZE=1000  # Records per batch insert

# Model Refresh Configuration
AUTO_REFRESH_ENABLED=false
AUTO_REFRESH_SCHEDULE=0 2 * * *  # Daily at 2 AM UTC (cron format)
AUTO_REFRESH_LOOKBACK_DAYS=7

# Decision Engine Configuration
DECISION_ENGINE_DIR=/app/engines
DECISION_ENGINE_ACTIVE=spot_optimizer_v1

# Data Fetching
PRICING_DATA_FETCH_PARALLELISM=5  # Parallel API calls
PRICING_DATA_RETRY_ATTEMPTS=3
PRICING_DATA_RETRY_BACKOFF=2  # Exponential backoff

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/ml-server/app.log
```

### Docker Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  ml-backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - ML_SERVER_PORT=8001
      - DB_HOST=postgres-ml
      - REDIS_HOST=redis-ml
    volumes:
      - ./models/uploaded:/app/models/uploaded
      - ./decision_engine/uploaded:/app/engines
      - ./logs:/var/log/ml-server
    depends_on:
      - postgres-ml
      - redis-ml
    networks:
      - ml-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/api/v1/ml/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  ml-frontend:
    build:
      context: ./ml-frontend
      dockerfile: Dockerfile
    ports:
      - "3001:3001"
    environment:
      - REACT_APP_API_URL=http://ml-backend:8001
      - REACT_APP_WS_URL=ws://ml-backend:8001
    depends_on:
      - ml-backend
    networks:
      - ml-network

  postgres-ml:
    image: postgres:15
    environment:
      POSTGRES_DB: ml_server
      POSTGRES_USER: ml_server
      POSTGRES_PASSWORD: xxx
    volumes:
      - postgres-ml-data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - ml-network
    ports:
      - "5433:5432"

  redis-ml:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis-ml-data:/data
    networks:
      - ml-network
    ports:
      - "6380:6379"

volumes:
  postgres-ml-data:
  redis-ml-data:

networks:
  ml-network:
    driver: bridge
```

---

## 📊 Key Workflows

### Workflow 1: Model Upload & Gap Filling

```
1. User → Frontend: Upload model file (.pkl)
   - Form: model_name, version, trained_until_date

2. Frontend → Backend: POST /api/v1/ml/models/upload
   - Backend validates file, saves to /models/uploaded/
   - Backend inserts record in ml_models table

3. User → Frontend: Click "Analyze Gap"
   - Frontend → Backend: POST /api/v1/ml/gap-filler/analyze
   - Backend: Compare trained_until_date vs current_date
   - Returns: gap_days=28, estimated_records=150,000

4. User → Frontend: Configure gap fill (instance types, regions)
   - Click "Fill Gap"

5. Frontend → Backend: POST /api/v1/ml/gap-filler/fill
   - Backend creates gap record in data_gaps table
   - Background task starts:
     a. Query AWS DescribeSpotPriceHistory API
     b. Fetch pricing data in batches
     c. Insert into spot_prices table
     d. Update gap record progress
   - Frontend polls /api/v1/ml/gap-filler/status/{gap_id} every 2s

6. Gap filling completes
   - Backend updates gap record: status=completed
   - Frontend shows success notification
   - Model now has up-to-date pricing data
```

### Workflow 2: Model Refresh (Scheduled)

```
1. Cron scheduler (daily at 2 AM UTC):
   - Triggers model refresh for active models

2. Backend refresh service:
   - Fetches last 7 days of pricing data from AWS APIs
   - Updates spot_prices and on_demand_prices tables
   - Updates spot_advisor_data from AWS Spot Advisor JSON

3. Backend:
   - Reloads model with new data
   - Updates model metadata: last_refresh_date
   - Inserts record in model_refresh_history

4. If auto_activate=true:
   - Activates refreshed model automatically

5. Frontend dashboard:
   - Shows "Model Refreshed" notification
   - Displays new data coverage dates
```

### Workflow 3: Live Prediction Request

```
1. Core Platform → ML Server: POST /api/v1/ml/decision/spot-optimize
   - Body: ClusterState, requirements, constraints

2. ML Server Backend:
   a. Query spot_prices table for recent prices
      SELECT * FROM spot_prices
      WHERE instance_type IN (...)
        AND region = '...'
        AND timestamp > NOW() - INTERVAL '7 days'
      ORDER BY timestamp DESC
      LIMIT 1000

   b. Query spot_advisor_data for interruption rates
      SELECT * FROM spot_advisor_data
      WHERE instance_type IN (...)
        AND region = '...'

   c. Load active model from /models/uploaded/

   d. Run model inference with pricing data

   e. Pass predictions to decision engine

   f. Generate recommendations and execution plan

3. ML Server → Core Platform: DecisionResponse
   - Returns: recommendations, estimated_savings, execution_plan

4. ML Server:
   - Insert prediction record in predictions_log
   - Insert decision record in decision_execution_log
   - Cache result in Redis (key: cluster_id, TTL: 5 min)

5. Frontend (WebSocket stream):
   - Live updates on dashboard
   - Shows prediction in real-time chart
```

---

## 🎯 CAST AI Decision Engines (Complete Feature Set)

### Overview
All decision engines live in the ML Server for centralized decision-making. The ML Server analyzes cluster state, pricing data, and workload patterns, then returns recommendations to the Core Platform for execution.

**Key Principle**: ML Server makes ALL decisions, Core Platform executes them via remote APIs.

---

### 1. Spot Optimizer Engine

**Purpose**: Select optimal Spot instances using AWS Spot Advisor public data

**Data Sources**:
- AWS Spot Advisor JSON: `https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json`
- Historical Spot prices from `spot_prices` table
- On-Demand prices from `on_demand_prices` table
- **NO SPS (Spot Placement Scores)** - User explicitly requested NOT to use

**Risk Score Formula** (0.0 = unsafe, 1.0 = safe):
```
Risk Score = (0.60 × Public_Rate_Score) +
             (0.25 × Volatility_Score) +
             (0.10 × Gap_Score) +
             (0.05 × Time_Score)

Where:
- Public_Rate_Score: From AWS Spot Advisor (<5% = 1.0, >20% = 0.0)
- Volatility_Score: Price stability over last 7 days
- Gap_Score: Current price vs On-Demand (lower = better)
- Time_Score: Hour of day (off-peak hours = higher score)
```

**Output**:
- Top 5 Spot instance recommendations ranked by risk score
- Fallback On-Demand instances if all Spot options too risky
- Estimated monthly savings per recommendation

**File**: `decision_engine/spot_optimizer.py`

---

### 2. Bin Packing Engine (Tetris Algorithm)

**Purpose**: Consolidate workloads to minimize node count and maximize resource utilization

**Algorithm**:
1. Analyze current pod placement across nodes
2. Calculate node utilization (CPU + memory)
3. Identify underutilized nodes (< 50% allocated)
4. Simulate pod migrations to consolidate workloads
5. Return drain plan for empty/underutilized nodes

**Constraints**:
- Respect pod anti-affinity rules
- Maintain node diversity (AZ spread)
- Ensure sufficient capacity for pod migrations
- Graceful drain with 90-second grace period

**Output**:
- List of nodes to drain and terminate
- Pod migration plan (source node → target node)
- Estimated savings from reduced node count

**File**: `decision_engine/bin_packing.py`

---

### 3. Rightsizing Engine (Deterministic Lookup)

**Purpose**: Match instance sizes to actual workload requirements

**Approach**: Deterministic lookup tables (NOT ML-based for Day Zero)

**Lookup Table Example**:
```python
# If pod requests 2 CPU + 4GB RAM:
INSTANCE_LOOKUP = {
    (2.0, 4.0): ["t3.large", "t3a.large", "m5.large"],
    (4.0, 8.0): ["m5.xlarge", "c5.xlarge", "t3.xlarge"],
    (8.0, 16.0): ["m5.2xlarge", "c5.2xlarge"],
    # ...
}
```

**Analysis**:
1. Query actual pod resource usage (last 7 days avg)
2. Compare actual usage vs requested resources
3. If actual < 50% of requested, recommend downsize
4. If actual > 80% of requested, recommend upsize
5. Use lookup table to find matching instance types

**Output**:
- Oversized instances with downsize recommendations
- Undersized instances with upsize recommendations
- Estimated cost savings from rightsizing

**File**: `decision_engine/rightsizing.py`

---

### 4. Office Hours Scheduler

**Purpose**: Auto-scale dev/staging environments based on time schedules

**Configuration**:
```json
{
  "environment": "dev",
  "office_hours": {
    "weekdays": {"start": "08:00", "end": "18:00"},
    "weekends": {"enabled": false}
  },
  "scale_down_replicas": 0,
  "scale_down_instance_count": 1  // Minimum nodes
}
```

**Logic**:
- Check current time (UTC)
- If outside office hours:
  - Scale deployments to 0 replicas (or configured minimum)
  - Drain and terminate excess nodes
- If inside office hours:
  - Scale deployments back to original replicas
  - Launch nodes as needed

**Output**:
- Scale commands for deployments
- Node termination/launch plan
- Estimated monthly savings

**File**: `decision_engine/scheduler.py`

---

### 5. Ghost Probe Scanner

**Purpose**: Detect zombie EC2 instances not in Kubernetes clusters

**Day Zero Capability**: Works immediately without customer historical data

**Algorithm**:
1. Core Platform sends list of running EC2 instances from customer account
2. Core Platform sends list of K8s nodes from cluster
3. ML Server compares: EC2 instances vs K8s nodes
4. Identifies "ghost" instances: EC2 running but NOT in K8s

**Ghost Detection**:
```python
ec2_instances = {i-1234, i-5678, i-9012}
k8s_nodes = {i-1234, i-5678}
ghost_instances = ec2_instances - k8s_nodes  # {i-9012}
```

**Safety**:
- 24-hour grace period before flagging as ghost
- Exclude instances with specific tags (e.g., `cloudoptim:ignore`)
- Manual approval before termination

**Output**:
- List of ghost instances with metadata
- Termination recommendations
- Estimated cost savings from cleanup

**File**: `decision_engine/ghost_probe.py`

---

### 6. Zombie Volume Cleanup

**Purpose**: Identify and remove unattached EBS volumes

**Algorithm**:
1. Core Platform sends list of all EBS volumes
2. Filter volumes with status = "available" (unattached)
3. Check volume age (last attach time)
4. If unattached > 7 days, flag as zombie

**Safety Checks**:
- Exclude volumes with snapshots (might be backups)
- Exclude volumes with specific tags (e.g., `backup:true`)
- Grace period: 7 days minimum
- Alert customer before deletion

**Output**:
- List of zombie volumes with age and size
- Deletion recommendations
- Estimated monthly savings from storage cleanup

**File**: `decision_engine/volume_cleanup.py`

---

### 7. Network Optimizer (Cross-AZ Traffic Affinity)

**Purpose**: Optimize cross-AZ data transfer costs by co-locating pods with their dependencies

**Problem**: AWS charges $0.01/GB for cross-AZ traffic (ingress/egress between AZs)

**Analysis**:
1. Core Platform sends pod communication matrix (pod A → pod B traffic volume)
2. Identify high-traffic pod pairs
3. Check if pods are in different AZs
4. Recommend pod re-scheduling to same AZ

**Algorithm**:
```python
# If pod-api (us-east-1a) → pod-db (us-east-1b) = 100GB/day
# Cost: 100GB × $0.01 = $1/day = $30/month
# Recommendation: Move pod-db to us-east-1a (same AZ as pod-api)
```

**Constraints**:
- Maintain AZ diversity for high-availability workloads
- Only optimize for pods with > 10GB/day cross-AZ traffic

**Output**:
- Pod affinity rules to add
- Estimated monthly savings from reduced cross-AZ traffic

**File**: `decision_engine/network_optimizer.py`

---

### 8. OOMKilled Auto-Remediation

**Purpose**: Detect OOMKilled pods and automatically increase memory limits

**Detection**:
1. Core Platform sends pod events (last 24 hours)
2. Filter events with reason = "OOMKilled"
3. Analyze pod memory requests vs actual usage

**Auto-Fix Logic**:
```python
if pod.status == "OOMKilled":
    current_memory = pod.spec.resources.requests.memory
    recommended_memory = current_memory × 1.5  # 50% increase
    return UpdateDeployment(memory=recommended_memory)
```

**Safety**:
- Maximum memory increase: 2x current limit
- If OOMKilled > 3 times, escalate to manual review
- Monitor memory usage after fix

**Output**:
- Deployment update commands with new memory limits
- OOMKilled pod history
- Recommended memory settings

**File**: `decision_engine/oomkilled_remediation.py`

---

### Decision Engine API Endpoints

All engines are invoked via ML Server API:

```http
POST /api/v1/ml/decision/spot-optimize
POST /api/v1/ml/decision/bin-pack
POST /api/v1/ml/decision/rightsize
POST /api/v1/ml/decision/schedule
POST /api/v1/ml/decision/ghost-probe
POST /api/v1/ml/decision/volume-cleanup
POST /api/v1/ml/decision/network-optimize
POST /api/v1/ml/decision/oomkilled-remediate
```

**Common Request Schema**:
```json
{
  "request_id": "req-12345",
  "cluster_id": "cluster-abc",
  "decision_type": "spot_optimize",
  "current_state": { /* ClusterState */ },
  "requirements": { /* Decision-specific params */ },
  "constraints": { /* Safety constraints */ }
}
```

**Common Response Schema**:
```json
{
  "request_id": "req-12345",
  "decision_type": "spot_optimize",
  "recommendations": [ /* List of recommendations */ ],
  "confidence_score": 0.95,
  "estimated_savings": 450.00,
  "execution_plan": [ /* Step-by-step execution */ ]
}
```

---

## 🚫 What ML Server Does NOT Do (Agentless Architecture)

**NO Client-Side Components**:
- ❌ No DaemonSets in customer clusters
- ❌ No client-side agents to install or manage
- ❌ No direct access to customer Kubernetes API
- ❌ No direct access to customer cluster databases

**All Cluster Operations via Core Platform**:
- Core Platform handles remote Kubernetes API calls
- Core Platform polls AWS EventBridge/SQS for Spot warnings
- Core Platform executes optimization plans on clusters
- ML Server only provides predictions and recommendations

**Public Data First (Day Zero)**:
- Uses AWS Spot Advisor public data for interruption rates
- Fetches pricing data from AWS public APIs
- No customer historical data needed for initial operation
- Works immediately after onboarding

---

**END OF SESSION MEMORY - ML SERVER (AGENTLESS ARCHITECTURE WITH BACKEND/DATABASE/FRONTEND)**
