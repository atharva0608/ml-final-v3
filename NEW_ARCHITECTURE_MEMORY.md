# CloudOptim – ML Models on Dedicated Server (New Architecture Memory)

**Last Updated**: 2025-11-28
**Status**: Architecture Defined, Implementation Pending User Approval

---

## High-Level Goal

- Run **all ML models and decision engines on a dedicated ML server**.
- This server is **inference and experimentation only**:
  - ❌ No model training happens on this server.
  - ✅ We **upload already-trained models** and **plug-in decision engines** via the ML frontend.
- Fix the classic gap issue:
  *"Model trained till October, but I need predictions from October → today."*
  This gap is filled automatically using **historic market data on the same server**.

---

## ML Server Responsibilities

### 1. Model Hosting (Inference Only)

- The ML server hosts:
  - Serialized ML models (e.g., `model.pkl` files).
  - Pluggable decision engine modules (rules-based, ML-based, or hybrid).
- Models and decision engines are **uploaded through the ML frontend**:
  - Use the **existing frontend design and layout** (same look & feel as the current app).
  - Only the backend endpoints and wiring change.

### 2. No Training on This Server

- This environment **does not train or retrain models**.
- All training happens offline / elsewhere (e.g., separate training pipelines, notebooks, or dedicated training infrastructure).
- Once trained, models are exported and uploaded here for:
  - A/B testing of different model versions.
  - Experimenting with new decision engines.
  - Running production-grade inference.

---

## Gap-Filling: October → "Now" Problem

### Problem

- Old behavior:
  Model is trained on data **up to October**, but the instance needs predictions that use data from **October → current date**.
- Previously, this required:
  - Extra data-engineering work.
  - Manual metric pulling or waiting for live data to accumulate.

### New Solution (On the ML Server)

- The dedicated ML server:
  1. **Knows the model's `trained_until` date** (stored in model metadata).
  2. On startup or when requested via the ML frontend, the server:
     - Detects the **gap between `trained_until` and "today"**.
     - **Directly pulls historic market data** (e.g., Spot/on-demand prices, metrics) **on the same server** for all required:
       - Instance types
       - Regions
  3. The gap is filled with:
     - Required historic prices / metrics.
     - Any necessary feature engineering applied locally.
  4. Once gap-filling completes:
     - The model immediately starts producing **up-to-date predictions**.
     - No waiting for weeks of new data collection.

> **Result**: As soon as the instance starts or is refreshed, we can get "today-ready" predictions using the uploaded model + auto gap-filling with historic prices.

---

## Live Predictions & Decision Streaming

### 1. Live Predictions

- After the gap is filled, the ML server:
  - Continuously runs inference using:
    - Fresh incoming data
    - Up-to-date historic context (already filled)
  - Stores predictions in a local store (DB / cache) optimized for:
    - Time series plots
    - Quick lookups per instance/region/workload

### 2. Live Decisions (Decision Engine)

- The **decision engine** is pluggable and uploaded just like models:
  - Fixed **input format** (normalized metrics, prices, states).
  - Fixed **output format** (actions, scores, explanations).
- The ML server:
  - Feeds model predictions into the decision engine.
  - Produces **live, actionable decisions** (e.g., "move to Spot in region X", "consolidate nodes", "rightsizing recommendations").
  - Exposes these decisions via APIs consumed by:
    - The central backend
    - Dashboards
    - Orchestration components.

### 3. Frontend Behavior (Using Current Design)

- We **keep the current frontend design** (layout, styling, UX).
- The updated ML frontend now supports:
  - **Model upload UI** (same design system, new functionality).
  - **Decision engine upload / selection** (e.g., dropdown to choose engine version).
  - **Gap-fill trigger & status display** (e.g., "Fill missing data from 2025-10-01 to today").
  - **Live charts**:
    - Predictions vs actuals, per instance / region.
    - Live decision stream visualized as:
      - Timelines, markers, or event overlays on graphs.
- All graphs update in near real time using the same visual style as the original app.

---

## Repository & Folder Layout

To separate legacy and new architecture cleanly:

### 1. Legacy Code – `old app/`

- All existing application files (current codebase) are moved into:

  ```text
  /old app/
    ├─ <all existing frontend files>
    ├─ <all existing backend files>
    ├─ <existing Dockerfiles, configs, scripts>
    └─ memory.md (old references retained for history)
  ```

- Purpose:
  - Preserve the original implementation.
  - Enable quick reference and rollback.
  - Keep old experiments and designs intact.

### 2. New Architecture – `new app/`

- All new application files and folders for the redesigned system live under:

  ```text
  /new app/
    ├─ ml-server/          # dedicated ML + decision server
    ├─ core-platform/      # central backend, DB, admin frontend
    ├─ client-agent/       # lightweight client-side agent (future use)
    ├─ memory.md           # updated architecture and behavior (this file)
    └─ infra/              # optional: docker-compose, IaC, scripts
  ```

- The **ml-server**:
  - Hosts:
    - Model upload endpoints
    - Decision engine upload/selection
    - Gap-filling logic via historic prices
    - Inference and live decisions
  - Serves data to:
    - An ML frontend (which reuses the **current UI design**)
    - The core platform.

- The **core-platform**:
  - Central storage for:
    - Clusters, customers, savings, events, etc.
  - Runs:
    - Cost optimization logic
    - Long-running analyzers
    - Global dashboards (admin UI).

- The **client-agent**:
  - Minimal footprint on client side.
  - Used later for heartbeats / optional local metric collection (still "agentless" for core value).

---

## API Endpoints for ML Server

### Model Management

```http
POST /api/v1/ml/models/upload
  → Upload trained model file (.pkl, serialized)
  → Metadata: model_name, version, trained_until_date

GET /api/v1/ml/models/list
  → List all uploaded models
  → Returns: [{model_id, name, version, trained_until, uploaded_at}]

POST /api/v1/ml/models/activate
  → Set active model version
  → Body: {model_id, version}

DELETE /api/v1/ml/models/{model_id}
  → Delete a model version
```

### Decision Engine Management

```http
POST /api/v1/ml/engines/upload
  → Upload decision engine module (Python file)
  → Returns: {engine_id, name, version}

GET /api/v1/ml/engines/list
  → List available decision engines
  → Returns: [{engine_id, name, version, active}]

POST /api/v1/ml/engines/select
  → Select active decision engine
  → Body: {engine_id, config}

GET /api/v1/ml/engines/{engine_id}/metadata
  → Get decision engine details (input/output schema, description)
```

### Gap Filling

```http
POST /api/v1/ml/gap-filler/analyze
  → Analyze data gaps for active model
  → Returns: {
      trained_until: "2025-10-31",
      current_date: "2025-11-28",
      gap_days: 28,
      required_data_types: ["spot_prices", "on_demand_prices"]
    }

POST /api/v1/ml/gap-filler/fill
  → Trigger automatic gap filling
  → Pulls historic prices from AWS APIs
  → Body: {
      instance_types: ["m5.large", "c5.large"],
      regions: ["us-east-1", "us-west-2"]
    }
  → Returns: {
      status: "in_progress",
      task_id: "gap-fill-12345"
    }

GET /api/v1/ml/gap-filler/status/{task_id}
  → Check gap-filling progress
  → Returns: {
      status: "in_progress|completed|failed",
      percent_complete: 75,
      records_filled: 15000,
      eta_seconds: 30
    }
```

### Predictions & Decisions

```http
POST /api/v1/ml/predict/spot-interruption
  → Get Spot interruption prediction
  → Body: {instance_type, region, spot_price, launch_time}
  → Returns: {interruption_probability, confidence}

POST /api/v1/ml/decision/spot-optimize
  → Get Spot optimization decision
  → Body: {cluster_id, requirements, constraints}
  → Returns: {recommendations, execution_plan, estimated_savings}

GET /api/v1/ml/predictions/live
  → Stream live predictions (WebSocket)

GET /api/v1/ml/decisions/live
  → Stream live decisions (WebSocket)
```

---

## Frontend Features (ML Frontend)

### Model Management Page
- **Upload Model**:
  - Drag-and-drop or file picker for `.pkl` files
  - Input fields: model name, version, trained_until date
  - Upload progress bar
- **Model List**:
  - Table showing: name, version, trained_until, status (active/inactive), uploaded_at
  - Actions: Activate, Delete, Download
- **Model Details**:
  - Show model metadata, performance metrics, feature importance

### Decision Engine Page
- **Upload Engine**:
  - Upload Python module with decision logic
  - Specify: engine name, version, description
- **Engine List**:
  - Dropdown to select active engine
  - Show: input/output schema, description
- **Engine Testing**:
  - Test engine with sample data
  - View sample decisions

### Gap Filler Page
- **Gap Analysis**:
  - Display: model trained_until date vs current date
  - Show: gap in days, required data types
  - Button: "Analyze Gap"
- **Fill Gap**:
  - Configure: instance types, regions to fetch
  - Button: "Fill Gap"
  - Progress indicator: percent complete, records filled, ETA
- **Status Log**:
  - Show gap-filling history and results

### Live Dashboard
- **Predictions Chart**:
  - Time series: predictions vs actuals
  - Filter by: instance type, region
  - Color-coded by confidence level
- **Decisions Stream**:
  - Live event stream of decisions
  - Timeline view with markers
  - Click to expand decision details (explanation, actions)
- **Model Performance**:
  - Real-time accuracy metrics
  - Drift detection alerts

---

## Configuration

### ML Server Environment Variables

```bash
# Server
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001
ML_SERVER_WORKERS=4

# Models
MODEL_UPLOAD_DIR=/app/models/uploaded
MODEL_ACTIVE_VERSION=v1
ALLOW_MODEL_TRAINING=false  # Explicitly disabled

# Gap Filler
GAP_FILLER_ENABLED=true
GAP_FILLER_AWS_REGION=us-east-1
GAP_FILLER_INSTANCE_TYPES=m5.large,m5.xlarge,c5.large
GAP_FILLER_REGIONS=us-east-1,us-west-2,eu-west-1
GAP_FILLER_HISTORIC_DAYS_MAX=90

# Decision Engines
DECISION_ENGINE_DIR=/app/engines
DECISION_ENGINE_ACTIVE=spot_optimizer_v1

# Storage
LOCAL_PREDICTION_STORE=redis
REDIS_HOST=redis.internal
REDIS_PORT=6379

# Central Platform
CENTRAL_PLATFORM_URL=http://core-platform:8000
CENTRAL_PLATFORM_API_KEY=xxx
```

---

## Summary

- **Dedicated ML server**: inference + decision experimentation, not training.
- **Upload-only models & decision engines** through the **existing frontend design**.
- **Automatic gap-filling** using **historic prices on the same server**, eliminating the "trained until October but need November data" issue.
- **Live graphs and live decisions** are plotted on the frontend using the current UI style.
- Repo is logically split into:
  - `old app/` – legacy implementation.
  - `new app/` – new dedicated ML + core platform architecture.

---

## Implementation Status

**Phase 1** (Current): ✅ Complete
- Architecture defined
- Documentation updated
- API specifications written
- Frontend features specified

**Phase 2** (Next): ⏳ Pending User Approval
- Folder reorganization (`old app/` + `new app/`)
- ML server implementation
- Model upload endpoints
- Gap-filler with AWS integration
- ML frontend (reuse current design)
- Decision engine upload capability

**Phase 3** (Future):
- Testing & validation
- Production deployment
- Performance optimization

---

**Last Updated**: 2025-11-28
**Waiting for**: User approval to begin Phase 2 implementation
