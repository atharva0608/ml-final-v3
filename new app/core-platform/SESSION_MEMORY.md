# Central Server - Session Memory & Documentation

## 📋 Overview
**Component**: Central Server (Backend, Database, Admin Frontend)
**Purpose**: Main control plane - handles all customer data, orchestration, decision execution, and admin interface
**Instance Type**: Primary server (handles all core logic)
**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 🎯 Core Responsibilities

### 1. Central Database Management
- PostgreSQL database with all customer and cluster data
- Time-series metrics storage (Prometheus/Thanos)
- State management for all clusters
- Historical optimization records
- Customer configuration and billing data

### 2. API & Orchestration
- Main REST API for all operations
- Coordinates between ML Server and Client Agents
- Executes optimization decisions
- Handles AWS API interactions (EC2, SQS, EventBridge)
- Kubernetes API interactions (remote cluster management)

### 3. Admin Frontend
- Real-time cost monitoring dashboard
- Live comparison: predictions vs actual data
- Model upload and management interface
- Customer configuration UI
- Optimization history and analytics
- Gap filling tool UI (query instance data, fill gaps)

### 4. Decision Execution Engine
- Receives recommendations from ML Server
- Validates safety checks
- Executes optimization plans
- Handles rollback scenarios
- Monitors execution status

### 5. Event Processing
- SQS queue polling for Spot interruption warnings
- EventBridge event routing
- Real-time cluster state updates
- Webhook notifications (Slack, email)

---

## 🔌 Integration Points (Common Components)

### A. Communication with ML Server
**Protocol**: REST API + WebSocket
**Direction**: Central → ML (request/response)

**Endpoints Called on ML Server**:
- `POST /api/v1/ml/decision/spot-optimize` - Get Spot instance recommendations
- `POST /api/v1/ml/decision/bin-pack` - Get consolidation plan
- `POST /api/v1/ml/decision/rightsize` - Get rightsizing recommendations
- `POST /api/v1/ml/predict/spot-interruption` - Get interruption probability

**Data Flow**:
```
Central Server → ML Server: Decision request (cluster state + requirements)
ML Server → Central Server: Recommendations + execution plan
Central Server: Validates and executes plan
Central Server: Stores results in database
```

### B. Communication with Client Agents
**Protocol**: REST API (Client polls Central) + WebSocket (real-time updates)
**Endpoints Exposed**:
- `GET /api/v1/client/tasks` - Client polls for pending tasks
- `POST /api/v1/client/metrics` - Client sends cluster metrics
- `POST /api/v1/client/events` - Client sends cluster events
- `WS /api/v1/client/stream` - Real-time task streaming

**Data Flow**:
```
Client Agent → Central Server: Metrics, events, status updates
Central Server → Client Agent: Tasks to execute (scale, migrate, etc.)
Client Agent: Executes tasks on Kubernetes cluster
Client Agent → Central Server: Execution results
```

### C. Shared Data Schemas (COMMON)
**Location**: `/common/schemas/` (shared across all servers)

```python
# Common data models
class ClusterState(BaseModel):
    cluster_id: str
    node_count: int
    total_cpu: float
    total_memory: float
    pod_count: int
    spot_node_count: int
    on_demand_node_count: int
    current_cost_per_hour: float

class DecisionRequest(BaseModel):
    request_id: str
    cluster_id: str
    decision_type: str  # spot_optimize, bin_pack, rightsize
    requirements: Dict[str, Any]
    constraints: Dict[str, Any]

class OptimizationTask(BaseModel):
    task_id: str
    cluster_id: str
    task_type: str  # launch_nodes, drain_nodes, resize
    parameters: Dict[str, Any]
    priority: int
    deadline: datetime
```

### D. Database Schema (OWNED BY CENTRAL SERVER)
**Primary Database**: PostgreSQL 15+
**Time-Series DB**: Prometheus + Thanos (long-term storage)

**Core Tables**:
```sql
-- Customers
customers (
    customer_id UUID PRIMARY KEY,
    company_name VARCHAR(255),
    email VARCHAR(255),
    aws_role_arn VARCHAR(512),
    sqs_queue_url VARCHAR(512),
    external_id VARCHAR(128),
    status VARCHAR(50),
    created_at TIMESTAMP
)

-- Clusters
clusters (
    cluster_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers,
    cluster_name VARCHAR(255),
    k8s_api_endpoint VARCHAR(512),
    k8s_token TEXT,
    region VARCHAR(50),
    node_count INT,
    status VARCHAR(50),
    created_at TIMESTAMP
)

-- Nodes
nodes (
    node_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters,
    node_name VARCHAR(255),
    instance_id VARCHAR(50),
    instance_type VARCHAR(50),
    availability_zone VARCHAR(50),
    node_type VARCHAR(20), -- spot, on-demand
    status VARCHAR(50),
    created_at TIMESTAMP
)

-- Spot Events
spot_events (
    event_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters,
    instance_id VARCHAR(50),
    event_type VARCHAR(50), -- interruption_warning, terminated
    received_at TIMESTAMP,
    action_taken VARCHAR(255),
    replacement_instance_id VARCHAR(50)
)

-- Optimization History
optimization_history (
    optimization_id UUID PRIMARY KEY,
    cluster_id UUID REFERENCES clusters,
    optimization_type VARCHAR(50),
    recommendations JSONB,
    execution_plan JSONB,
    estimated_savings DECIMAL(10,2),
    actual_savings DECIMAL(10,2),
    status VARCHAR(50),
    executed_at TIMESTAMP
)

-- Customer Config
customer_config (
    config_id UUID PRIMARY KEY,
    customer_id UUID REFERENCES customers,
    config_key VARCHAR(100),
    config_value JSONB,
    updated_at TIMESTAMP
)

-- Metrics Time Series (summary)
metrics_summary (
    metric_id BIGSERIAL PRIMARY KEY,
    cluster_id UUID REFERENCES clusters,
    metric_type VARCHAR(50), -- cpu, memory, cost
    value DECIMAL(10,2),
    timestamp TIMESTAMP
)
```

### E. AWS Integration
**IAM Role**: Cross-account role assumption
**Services Used**:
- **EC2**: Launch/terminate instances, query Spot prices
- **SQS**: Poll Spot interruption events
- **EventBridge**: Receive cluster events
- **CloudWatch**: Fetch metrics (optional)

**Permissions Required**:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:DescribeSpotPriceHistory",
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:CreateTags"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage"
            ],
            "Resource": "arn:aws:sqs:*:*:cloudoptim-*"
        }
    ]
}
```

---

## 📁 Directory Structure

```
central-server/
├── SESSION_MEMORY.md          # This file
├── README.md
├── requirements.txt
├── config/
│   ├── common.yaml            # Shared with other servers
│   ├── database.yaml          # Database configuration
│   └── aws.yaml               # AWS configuration
├── api/
│   ├── main.py                # FastAPI application
│   ├── routes/
│   │   ├── customers.py       # Customer management
│   │   ├── clusters.py        # Cluster management
│   │   ├── optimization.py    # Optimization endpoints
│   │   ├── ml_proxy.py        # Proxy to ML Server
│   │   ├── client_api.py      # Client agent endpoints
│   │   └── admin.py           # Admin endpoints
│   ├── middleware/
│   │   ├── auth.py
│   │   └── rate_limit.py
│   └── dependencies/
│       ├── database.py
│       └── aws.py
├── database/
│   ├── migrations/            # Alembic migrations
│   ├── models.py              # SQLAlchemy models
│   ├── schemas.py             # Pydantic schemas
│   └── seed_data.sql          # Initial data
├── services/
│   ├── optimizer_service.py   # Orchestrates optimization
│   ├── executor_service.py    # Executes optimization plans
│   ├── spot_handler.py        # Handles Spot interruptions
│   ├── k8s_client.py          # Kubernetes API client
│   ├── aws_client.py          # AWS API client
│   ├── ml_client.py           # ML Server client
│   └── metrics_collector.py   # Collects cluster metrics
├── admin-frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── Dashboard.tsx          # Main dashboard
│   │   │   ├── CostMonitor.tsx        # Real-time cost display
│   │   │   ├── PredictionComparison.tsx # Predictions vs actual
│   │   │   ├── ModelUploader.tsx      # Upload ML models
│   │   │   ├── GapFiller.tsx          # Data gap filling UI
│   │   │   ├── ClusterList.tsx
│   │   │   └── OptimizationHistory.tsx
│   │   ├── services/
│   │   │   └── api.ts             # API client
│   │   └── types/
│   │       └── index.ts           # TypeScript types
│   └── public/
├── scripts/
│   ├── install.sh
│   ├── setup_database.sh
│   ├── migrate_database.sh
│   ├── start_server.sh
│   └── deploy_frontend.sh
├── tests/
│   ├── test_api.py
│   ├── test_services.py
│   └── test_integration.py
└── docs/
    ├── API_REFERENCE.md
    ├── DATABASE_SCHEMA.md
    └── DEPLOYMENT.md
```

---

## 🔧 Technology Stack

### Backend
- **Language**: Python 3.10+
- **Framework**: FastAPI 0.103+
- **Database ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic
- **Background Tasks**: Celery + Redis
- **WebSocket**: FastAPI WebSocket

### Frontend (Admin Dashboard)
- **Framework**: React 18+ with TypeScript
- **State Management**: Redux Toolkit or Zustand
- **UI Library**: Material-UI or Tailwind CSS
- **Charts**: Recharts or Chart.js
- **Real-time**: Socket.IO or native WebSocket

### Database & Storage
- **Primary DB**: PostgreSQL 15+
- **Time-series**: Prometheus + Thanos
- **Cache**: Redis 7+
- **Message Queue**: Redis (Celery) or RabbitMQ

### AWS SDK
- **boto3**: AWS SDK for Python
- **Kubernetes**: kubernetes-client

---

## 🚀 Deployment Configuration

### Environment Variables
```bash
# Server Configuration
CENTRAL_SERVER_HOST=0.0.0.0
CENTRAL_SERVER_PORT=8000
CENTRAL_SERVER_WORKERS=8

# Database
DB_HOST=postgres.internal
DB_PORT=5432
DB_NAME=cloudoptim
DB_USER=central_server
DB_PASSWORD=xxx
DB_POOL_SIZE=20

# ML Server Connection
ML_SERVER_URL=http://ml-server:8001
ML_SERVER_API_KEY=xxx

# Redis
REDIS_HOST=redis.internal
REDIS_PORT=6379
CELERY_BROKER_URL=redis://redis.internal:6379/0

# AWS
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Security
JWT_SECRET_KEY=xxx
API_KEY_SALT=xxx

# Frontend
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=["http://localhost:3000"]
```

### Docker Compose
```yaml
services:
  central-server:
    build: ./central-server
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=postgres
      - REDIS_HOST=redis
      - ML_SERVER_URL=http://ml-server:8001
    depends_on:
      - postgres
      - redis
      - ml-server

  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=cloudoptim
      - POSTGRES_USER=central_server
      - POSTGRES_PASSWORD=xxx

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  admin-frontend:
    build: ./central-server/admin-frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
```

---

## 🔄 Core Workflows

### 1. Spot Interruption Handling
```
AWS EventBridge → SQS Queue
                    ↓
Central Server polls SQS (every 5 seconds)
                    ↓
Parse interruption event (instance_id, 2-min warning)
                    ↓
Query database: Find cluster + node
                    ↓
Request ML Server: Get replacement recommendation
                    ↓
Execute: Launch On-Demand replacement
                    ↓
Send task to Client Agent: Drain dying node
                    ↓
Wait for new node Ready
                    ↓
(Later) Replace On-Demand with Spot when safe
```

### 2. Optimization Request Flow
```
Admin triggers optimization (or scheduled job)
                    ↓
Central Server: Fetch cluster state from DB
                    ↓
Central Server → ML Server: POST /api/v1/ml/decision/spot-optimize
                    ↓
ML Server: Analyze, return recommendations
                    ↓
Central Server: Validate safety checks
                    ↓
Central Server: Store plan in optimization_history
                    ↓
Central Server: Call AWS EC2 API (launch Spot instances)
                    ↓
Central Server: Send tasks to Client Agent (update labels, drain)
                    ↓
Client Agent: Executes tasks, reports back
                    ↓
Central Server: Update database, calculate savings
```

### 3. Data Gap Filling Workflow
```
Admin uploads new model (trained on old data)
                    ↓
Admin opens Gap Filler UI
                    ↓
UI: Query instance for required data range
                    ↓
Central Server: Request ML Server to identify gaps
                    ↓
ML Server: Return gap details (dates, data types)
                    ↓
UI: Display gaps to admin
                    ↓
Admin clicks "Fill Gaps"
                    ↓
Central Server → ML Server: POST /api/v1/ml/data/fill-gaps
                    ↓
ML Server: Query AWS APIs, fill missing data
                    ↓
ML Server: Return filled data
                    ↓
Central Server: Store in database
                    ↓
UI: Display success, show filled records
```

---

## 📊 Admin Frontend Features

### 1. Real-Time Cost Dashboard
**Components**:
- Current cost per hour (live updates)
- Baseline cost (without CloudOptim)
- Savings percentage
- Projected monthly savings
- 7-day savings trend chart

**Data Source**: WebSocket stream from Central Server
**Update Frequency**: Every 60 seconds

### 2. Prediction vs Actual Comparison
**Purpose**: Show how ML predictions compare to reality
**Metrics Displayed**:
- Predicted Spot interruption rate vs Actual
- Predicted cost savings vs Actual savings
- Predicted resource usage vs Actual usage

**Visualization**: Side-by-side bar charts, line graphs

### 3. Model Upload Interface
**Features**:
- Upload trained model files (.model, .pkl)
- Specify model version and metadata
- View currently active models
- Switch between model versions
- Test model with sample data

**Backend**: Stores models in `/models/saved/`, updates registry

### 4. Gap Filler Tool
**UI Flow**:
1. Display model training date
2. Show current date and required lookback
3. Calculate and display gaps
4. Button: "Fill Gaps"
5. Progress indicator during filling
6. Summary: Records filled, sources used, duration

**Implementation**: React component calling `/api/v1/admin/gap-filler`

---

## 🔗 Common Components Shared Across Servers

### 1. Authentication Middleware
**Location**: `/common/auth/` (to be created)
**Implementation**: JWT tokens + API keys
**Used By**: All servers validate requests

### 2. Shared Pydantic Models
**Location**: `/common/schemas/models.py`
**Models**:
- `ClusterState`
- `DecisionRequest`
- `DecisionResponse`
- `OptimizationTask`
- `MetricsData`
- `SpotEvent`

### 3. Configuration Schema
**Format**: YAML
**Common Config** (`config/common.yaml`):
```yaml
environment: production
logging:
  level: INFO
  format: json
database:
  host: postgres.internal
  port: 5432
redis:
  host: redis.internal
  port: 6379
ml_server:
  url: http://ml-server:8001
  timeout: 30
```

### 4. Event Schema (Message Queue)
**Events Published by Central Server**:
- `optimization.started`
- `optimization.completed`
- `spot.interruption.detected`
- `cluster.state.changed`

**Events Consumed**:
- `client.metrics.updated` (from Client Agent)
- `ml.prediction.ready` (from ML Server)

---

## 🔄 Session Updates Log

### 2025-11-28 - Initial Setup
**Changes Made**:
- Created central-server folder structure
- Documented database schema
- Defined integration points with ML Server and Client Agents
- Specified Admin Frontend features
- Documented core workflows (Spot handling, optimization, gap filling)
- Listed common components and shared schemas

**Next Steps**:
1. Create database models and migrations
2. Implement FastAPI server with all endpoints
3. Create AWS client service (SQS polling, EC2 API)
4. Create Kubernetes client service
5. Build admin frontend with React
6. Implement real-time cost monitoring dashboard
7. Create model upload and gap filler UI

---

## 📝 API Specifications

### Customer Management
```http
POST /api/v1/customers
{
  "company_name": "Acme Corp",
  "email": "admin@acme.com",
  "aws_role_arn": "arn:aws:iam::xxx:role/CloudOptim",
  "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/xxx/cloudoptim-events"
}
```

### Trigger Optimization
```http
POST /api/v1/optimization/run
{
  "cluster_id": "cluster-123",
  "optimization_type": "spot_optimize",
  "dry_run": false
}

Response:
{
  "optimization_id": "opt-456",
  "status": "in_progress",
  "estimated_savings": 1250.50
}
```

### Client Agent Task Polling
```http
GET /api/v1/client/tasks?cluster_id=cluster-123

Response:
{
  "tasks": [
    {
      "task_id": "task-789",
      "task_type": "drain_node",
      "parameters": {
        "node_name": "ip-10-0-1-23.ec2.internal"
      },
      "priority": 1,
      "deadline": "2025-11-28T10:05:00Z"
    }
  ]
}
```

---

## 🐛 Troubleshooting

### SQS Messages Not Received
**Symptom**: Spot events not detected
**Solution**: Check IAM role permissions, SQS queue URL

### ML Server Timeout
**Symptom**: Optimization requests fail
**Solution**: Check ML_SERVER_URL, increase timeout, verify ML Server is running

### Database Connection Pool Exhausted
**Symptom**: "Too many connections" error
**Solution**: Increase DB_POOL_SIZE, check for connection leaks

---

## 📌 Important Notes

1. **Central Control**: This server is the main control plane
2. **Database Owner**: Owns PostgreSQL schema, provides read-only to ML Server
3. **Orchestrator**: Coordinates ML Server and Client Agents
4. **AWS Integration**: Handles all AWS API calls (EC2, SQS)
5. **Admin UI**: Provides complete visibility and control
6. **Real-time Updates**: WebSocket for live cost monitoring

---

## 🎯 Integration Checklist

- [ ] Database schema created and migrated
- [ ] ML Server connection configured and tested
- [ ] AWS IAM role configured
- [ ] SQS queue polling working
- [ ] Kubernetes API client tested
- [ ] Admin frontend deployed
- [ ] Real-time WebSocket working
- [ ] Model upload functionality tested
- [ ] Gap filler UI working
- [ ] Cost monitoring dashboard live

---

**END OF SESSION MEMORY - CENTRAL SERVER**
*Append all future changes and updates below this line*

---
