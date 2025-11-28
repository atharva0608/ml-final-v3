# Common Components & Integration Guide
## CloudOptim - Cross-Server Integration Documentation

**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 📋 Overview

This document defines all common components, data schemas, APIs, and integration patterns shared across the three CloudOptim servers:
1. **ML Server** - Machine Learning & Decision Engine
2. **Central Server** - Backend, Database, Admin Frontend
3. **Client Server** - Client-Side Agent (runs in customer cluster)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Customer AWS Account                        │
│                                                                  │
│  ┌────────────────┐         ┌──────────────────┐              │
│  │   EKS Cluster  │         │  EventBridge     │              │
│  │                │         │  + SQS Queue     │              │
│  │  ┌──────────┐  │         └────────┬─────────┘              │
│  │  │ Client   │  │                  │                         │
│  │  │ Agent    │  │                  │                         │
│  │  └────┬─────┘  │                  │                         │
│  │       │        │                  │                         │
│  └───────┼────────┘                  │                         │
│          │                           │                         │
└──────────┼───────────────────────────┼─────────────────────────┘
           │                           │
           │ HTTPS                     │ HTTPS
           │                           │
┌──────────┼───────────────────────────┼─────────────────────────┐
│          ▼                           ▼                         │
│  ┌──────────────────────────────────────────────────┐         │
│  │          Central Server (Control Plane)          │         │
│  │                                                   │         │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │         │
│  │  │   API    │  │ Database │  │  Admin   │      │         │
│  │  │          │  │ (Postgres│  │ Frontend │      │         │
│  │  └────┬─────┘  │  +Redis) │  └──────────┘      │         │
│  │       │        └──────────┘                      │         │
│  └───────┼─────────────────────────────────────────┘         │
│          │                                                     │
│          │ REST API                                            │
│          ▼                                                     │
│  ┌──────────────────────────────────────────────────┐         │
│  │              ML Server                            │         │
│  │                                                   │         │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────┐  │         │
│  │  │  Models  │  │   Decision   │  │   Data   │  │         │
│  │  │          │  │   Engines    │  │  Fetcher │  │         │
│  │  └──────────┘  └──────────────┘  └──────────┘  │         │
│  └──────────────────────────────────────────────────┘         │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔗 Integration Patterns

### Pattern 1: Request-Response (Synchronous)
**Used For**: ML predictions, decision requests
**Flow**:
```
Central Server → ML Server: POST /api/v1/ml/decision/spot-optimize
ML Server: Process request, run decision engine
ML Server → Central Server: JSON response with recommendations
```

### Pattern 2: Polling (Client-Initiated)
**Used For**: Client Agent task retrieval
**Flow**:
```
Client Agent → Central Server: GET /api/v1/client/tasks (every 10s)
Central Server: Return pending tasks
Client Agent: Execute tasks
Client Agent → Central Server: POST /api/v1/client/tasks/{id}/result
```

### Pattern 3: Event Stream (Real-Time)
**Used For**: Live dashboard updates, urgent tasks
**Flow**:
```
Central Server ← AWS EventBridge: Spot interruption event
Central Server: Process event
Central Server → Admin Frontend: WebSocket push (cost update)
Central Server → Client Agent: WebSocket push (urgent task)
```

---

## 📊 Common Data Schemas

### Location
All shared schemas are defined in: `/common/schemas/`

### Schema Files
```
common/schemas/
├── models.py          # Core data models (Pydantic)
├── requests.py        # API request schemas
├── responses.py       # API response schemas
├── tasks.py           # Task definitions
└── metrics.py         # Metrics schemas
```

### Core Models

#### 1. ClusterState
**Purpose**: Represents current state of a Kubernetes cluster
**Used By**: All servers
**Definition**:
```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ClusterState(BaseModel):
    cluster_id: str
    cluster_name: str
    region: str

    # Node information
    total_nodes: int
    spot_nodes: int
    on_demand_nodes: int

    # Resource information
    total_cpu_cores: float
    total_memory_gb: float
    allocated_cpu_cores: float
    allocated_memory_gb: float

    # Pod information
    total_pods: int
    running_pods: int
    pending_pods: int

    # Cost information
    current_cost_per_hour: float
    baseline_cost_per_hour: float

    # Metadata
    last_updated: datetime
    health_status: str  # GREEN, YELLOW, RED
```

#### 2. DecisionRequest
**Purpose**: Request sent from Central Server to ML Server for optimization decisions
**Flow**: Central → ML
**Definition**:
```python
class DecisionRequest(BaseModel):
    request_id: str
    cluster_id: str
    timestamp: datetime
    decision_type: str  # spot_optimize, bin_pack, rightsize, schedule

    # Current state
    current_state: ClusterState

    # Requirements
    requirements: dict  # e.g., {"cpu_required": 2.0, "memory_required": 8.0}

    # Constraints
    constraints: dict  # e.g., {"max_spot_percentage": 0.80}

    # Context
    metadata: dict  # Additional context
```

#### 3. DecisionResponse
**Purpose**: Response from ML Server containing optimization recommendations
**Flow**: ML → Central
**Definition**:
```python
class Recommendation(BaseModel):
    instance_type: str
    node_count: int
    risk_score: float
    hourly_price: float
    monthly_savings: float

class ExecutionStep(BaseModel):
    step: int
    action: str  # launch_spot_instances, drain_node, etc.
    parameters: dict

class DecisionResponse(BaseModel):
    request_id: str
    timestamp: datetime
    decision_type: str

    # Recommendations
    recommendations: List[Recommendation]

    # Confidence and savings
    confidence_score: float  # 0.0 to 1.0
    estimated_savings: float  # USD per month

    # Risk assessment
    risk_assessment: dict

    # Execution plan
    execution_plan: List[ExecutionStep]

    # Metadata
    metadata: dict
```

#### 4. Task (for Client Agent)
**Purpose**: Task sent from Central Server to Client Agent for execution
**Flow**: Central → Client
**Definition**:
```python
class Task(BaseModel):
    task_id: str
    cluster_id: str
    task_type: str  # drain_node, label_node, cordon_node, etc.

    # Task parameters
    parameters: dict  # e.g., {"node_name": "ip-10-0-1-23", "grace_period": 90}

    # Priority and deadline
    priority: int  # 1=highest, 10=lowest
    deadline: datetime

    # Metadata
    created_at: datetime
    created_by: str  # e.g., "optimizer_service"
```

#### 5. TaskResult
**Purpose**: Result of task execution sent from Client Agent to Central Server
**Flow**: Client → Central
**Definition**:
```python
class TaskResult(BaseModel):
    task_id: str
    status: str  # success, failed, timeout, cancelled

    # Execution details
    executed_at: datetime
    duration_seconds: float

    # Logs and errors
    logs: str
    error: Optional[str]

    # Additional data
    metadata: dict
```

#### 6. ClusterMetrics
**Purpose**: Metrics collected by Client Agent and sent to Central Server
**Flow**: Client → Central
**Definition**:
```python
class NodeMetric(BaseModel):
    node_name: str
    instance_type: str
    instance_id: str
    availability_zone: str
    node_type: str  # spot, on-demand
    cpu_allocatable: float
    memory_allocatable_gb: float
    cpu_allocated: float
    memory_allocated_gb: float
    pod_count: int

class ClusterMetrics(BaseModel):
    cluster_id: str
    timestamp: datetime

    # Aggregated metrics
    total_nodes: int
    spot_nodes: int
    on_demand_nodes: int
    total_cpu: float
    total_memory_gb: float
    allocated_cpu: float
    allocated_memory_gb: float
    total_pods: int

    # Node-level details
    nodes: List[NodeMetric]

    # Cost calculation
    estimated_cost_per_hour: float
```

#### 7. SpotEvent
**Purpose**: Spot instance interruption event
**Flow**: AWS → Central (via SQS)
**Definition**:
```python
class SpotEvent(BaseModel):
    event_id: str
    event_type: str  # interruption_warning, instance_terminated

    # AWS details
    instance_id: str
    region: str
    availability_zone: str

    # Timing
    received_at: datetime
    interruption_time: datetime  # When AWS will terminate

    # Cluster mapping
    cluster_id: Optional[str]
    node_name: Optional[str]

    # Action taken
    action_taken: Optional[str]
    replacement_instance_id: Optional[str]
```

---

## 🔐 Authentication & Authorization

### API Key Authentication
**Method**: Bearer token in Authorization header
**Format**: `Authorization: Bearer {API_KEY}`

**Implementation**:
```python
# common/auth/api_key.py
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    api_key = credentials.credentials

    # Validate against database or environment variable
    if not is_valid_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key
```

**Usage in APIs**:
```python
from fastapi import Depends
from common.auth import verify_api_key

@app.post("/api/v1/ml/decision/spot-optimize")
async def spot_optimize(
    request: DecisionRequest,
    api_key: str = Depends(verify_api_key)
):
    # Process request
    pass
```

### Service-to-Service Authentication
**ML Server ↔ Central Server**:
- Central Server has API key for ML Server
- ML Server validates requests from Central Server

**Client Agent ↔ Central Server**:
- Client Agent has API key (stored in Kubernetes Secret)
- Central Server validates requests from Client Agent
- Each cluster has unique API key

---

## 📡 API Endpoints

### Central Server Endpoints

#### For ML Server
```
POST /api/v1/ml/proxy/decision
  → Proxy decision requests to ML Server
  → Used for testing/debugging

GET /api/v1/ml/health
  → Check ML Server connectivity
```

#### For Client Agents
```
GET /api/v1/client/tasks?cluster_id={id}
  → Get pending tasks for a cluster
  → Returns: List[Task]

POST /api/v1/client/tasks/{task_id}/result
  → Submit task execution result
  → Body: TaskResult

POST /api/v1/client/metrics
  → Submit cluster metrics
  → Body: ClusterMetrics

POST /api/v1/client/events
  → Submit cluster events
  → Body: List[Event]

POST /api/v1/client/heartbeat
  → Health check heartbeat
  → Body: {"cluster_id": str, "status": str, "timestamp": datetime}

WS /api/v1/client/stream?cluster_id={id}
  → WebSocket for real-time task streaming
```

#### For Admin Frontend
```
GET /api/v1/admin/clusters
  → List all clusters

GET /api/v1/admin/clusters/{id}/state
  → Get cluster current state

GET /api/v1/admin/savings
  → Get real-time savings data

POST /api/v1/admin/optimization/trigger
  → Manually trigger optimization

POST /api/v1/admin/models/upload
  → Upload new ML model

POST /api/v1/admin/gap-filler/analyze
  → Analyze data gaps

POST /api/v1/admin/gap-filler/fill
  → Fill data gaps

WS /api/v1/admin/stream
  → Real-time updates for dashboard
```

### ML Server Endpoints

```
POST /api/v1/ml/decision/spot-optimize
  → Get Spot instance recommendations
  → Body: DecisionRequest
  → Returns: DecisionResponse

POST /api/v1/ml/decision/bin-pack
  → Get workload consolidation plan
  → Body: DecisionRequest
  → Returns: DecisionResponse

POST /api/v1/ml/decision/rightsize
  → Get instance rightsizing recommendations
  → Body: DecisionRequest
  → Returns: DecisionResponse

POST /api/v1/ml/decision/schedule
  → Get office hours scheduling plan
  → Body: DecisionRequest
  → Returns: DecisionResponse

POST /api/v1/ml/predict/spot-interruption
  → Predict Spot interruption probability
  → Body: {"instance_type": str, "region": str, ...}
  → Returns: {"probability": float, "confidence": float}

POST /api/v1/ml/data/fill-gaps
  → Fill training data gaps
  → Body: {"model_training_date": datetime, "lookback_days": int}
  → Returns: {"gaps_filled": int, "records": int}

GET /api/v1/ml/health
  → Health check
  → Returns: {"status": "healthy", "models_loaded": bool}
```

---

## 🗄️ Database Schema

### Ownership
**Owner**: Central Server
**Access**:
- Central Server: Read/Write
- ML Server: Read-Only
- Client Agent: None (accesses via Central Server API)

### Connection Strings
```bash
# Central Server (read/write)
postgresql://central_server:password@postgres:5432/cloudoptim

# ML Server (read-only)
postgresql://ml_server_ro:password@postgres:5432/cloudoptim
```

### Core Tables

#### customers
```sql
CREATE TABLE customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,

    -- AWS Integration
    aws_role_arn VARCHAR(512),
    sqs_queue_url VARCHAR(512),
    external_id VARCHAR(128),

    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, suspended, trial

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### clusters
```sql
CREATE TABLE clusters (
    cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(customer_id) ON DELETE CASCADE,

    cluster_name VARCHAR(255) NOT NULL,
    region VARCHAR(50) NOT NULL,

    -- Kubernetes connection
    k8s_api_endpoint VARCHAR(512),
    k8s_token TEXT,  -- Encrypted
    k8s_version VARCHAR(50),

    -- State
    node_count INT DEFAULT 0,
    pod_count INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP,

    UNIQUE(customer_id, cluster_name)
);
```

#### nodes
```sql
CREATE TABLE nodes (
    node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES clusters(cluster_id) ON DELETE CASCADE,

    node_name VARCHAR(255) NOT NULL,
    instance_id VARCHAR(50),
    instance_type VARCHAR(50),
    availability_zone VARCHAR(50),

    -- Node type
    node_type VARCHAR(20),  -- spot, on-demand

    -- Resources
    cpu_allocatable DECIMAL(10, 2),
    memory_allocatable_gb DECIMAL(10, 2),

    -- Status
    status VARCHAR(50) DEFAULT 'Ready',

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    terminated_at TIMESTAMP,

    UNIQUE(cluster_id, node_name)
);
```

#### spot_events
```sql
CREATE TABLE spot_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES clusters(cluster_id),

    instance_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,

    -- Timing
    received_at TIMESTAMP DEFAULT NOW(),
    interruption_time TIMESTAMP,

    -- Action
    action_taken VARCHAR(255),
    replacement_instance_id VARCHAR(50),

    -- Metadata
    metadata JSONB
);
```

#### optimization_history
```sql
CREATE TABLE optimization_history (
    optimization_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id UUID REFERENCES clusters(cluster_id),

    optimization_type VARCHAR(50) NOT NULL,

    -- Request and response
    request_data JSONB,
    recommendations JSONB,
    execution_plan JSONB,

    -- Savings
    estimated_savings DECIMAL(10, 2),
    actual_savings DECIMAL(10, 2),

    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, executing, completed, failed

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Error handling
    error_message TEXT
);
```

---

## ⚙️ Configuration Management

### Configuration Files Structure
```
common/config/
├── common.yaml          # Shared by all servers
├── development.yaml     # Dev environment overrides
├── staging.yaml         # Staging environment overrides
└── production.yaml      # Production environment overrides
```

### common.yaml
```yaml
# Common configuration shared across all servers
environment: production  # development, staging, production

# Logging
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  format: json  # json, text
  output: stdout  # stdout, file

# Database
database:
  host: postgres.internal
  port: 5432
  name: cloudoptim
  pool_size: 10
  max_overflow: 20
  echo: false  # SQL query logging

# Redis
redis:
  host: redis.internal
  port: 6379
  db: 0
  password: null
  ttl_seconds: 3600

# API Settings
api:
  request_timeout_seconds: 30
  rate_limit_per_minute: 60

# AWS
aws:
  region: us-east-1
  spot_advisor_url: "https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json"
  spot_advisor_refresh_interval_seconds: 21600  # 6 hours
```

### Loading Configuration
```python
# common/config/loader.py
import yaml
from pathlib import Path
from typing import Dict, Any

def load_config(env: str = "production") -> Dict[str, Any]:
    """Load configuration for specified environment"""
    config_dir = Path(__file__).parent

    # Load base config
    with open(config_dir / "common.yaml") as f:
        config = yaml.safe_load(f)

    # Load environment-specific overrides
    env_file = config_dir / f"{env}.yaml"
    if env_file.exists():
        with open(env_file) as f:
            env_config = yaml.safe_load(f)
            config.update(env_config)

    return config
```

---

## 🔄 Data Flow Examples

### Example 1: Spot Optimization Flow

```
1. Admin triggers optimization via UI
   Admin Frontend → Central Server: POST /api/v1/admin/optimization/trigger
   Body: {"cluster_id": "cluster-123", "optimization_type": "spot_optimize"}

2. Central Server fetches cluster state
   Central Server → Database: SELECT * FROM clusters WHERE cluster_id = 'cluster-123'
   Central Server → Database: SELECT * FROM nodes WHERE cluster_id = 'cluster-123'

3. Central Server requests ML decision
   Central Server → ML Server: POST /api/v1/ml/decision/spot-optimize
   Body: DecisionRequest {
       cluster_id: "cluster-123",
       current_state: {...},
       requirements: {"cpu_required": 2.0, "node_count": 10}
   }

4. ML Server processes and responds
   ML Server: Run SpotOptimizerEngine
   ML Server → Central Server: DecisionResponse {
       recommendations: [
           {instance_type: "c5.large", node_count: 6, monthly_savings: 450},
           {instance_type: "m5a.large", node_count: 4, monthly_savings: 350}
       ],
       estimated_savings: 800,
       execution_plan: [...]
   }

5. Central Server executes plan
   Central Server → AWS EC2: RunInstances (launch Spot instances)
   Central Server → Database: INSERT INTO optimization_history (...)

6. Central Server sends tasks to Client Agent
   Client Agent → Central Server: GET /api/v1/client/tasks?cluster_id=cluster-123
   Central Server → Client Agent: [
       {task_type: "label_node", parameters: {...}},
       {task_type: "drain_node", parameters: {...}}
   ]

7. Client Agent executes and reports
   Client Agent: Execute tasks on Kubernetes
   Client Agent → Central Server: POST /api/v1/client/tasks/task-456/result
   Body: TaskResult {status: "success", logs: "...", duration_seconds: 45.2}

8. Central Server updates database and dashboard
   Central Server → Database: UPDATE optimization_history SET status='completed'
   Central Server → Admin Frontend (WebSocket): {
       type: "optimization_complete",
       savings: 800,
       status: "success"
   }
```

### Example 2: Spot Interruption Handling

```
1. AWS emits Spot interruption warning
   AWS EventBridge → SQS Queue: EC2 Spot Instance Interruption Warning
   Event: {instance-id: "i-1234abcd", interruption-time: "2025-11-28T10:32:00Z"}

2. Central Server polls SQS
   Central Server → SQS: ReceiveMessage (every 5 seconds)
   Central Server: Parse event

3. Central Server identifies affected node
   Central Server → Database: SELECT * FROM nodes WHERE instance_id = 'i-1234abcd'
   Result: {node_name: "ip-10-0-1-23", cluster_id: "cluster-123"}

4. Central Server requests replacement recommendation
   Central Server → ML Server: POST /api/v1/ml/decision/spot-optimize
   Body: {requirements: {cpu: 2, memory: 8, urgent: true}}

5. Central Server launches replacement
   Central Server → AWS EC2: RunInstances (On-Demand for reliability)
   Result: {instance-id: "i-5678efgh"}

6. Central Server sends drain task to Client
   Client Agent → Central Server: GET /api/v1/client/tasks
   Central Server → Client Agent: [
       {task_type: "drain_node", parameters: {node_name: "ip-10-0-1-23", grace_period: 90}}
   ]

7. Client Agent drains node
   Client Agent → Kubernetes: Cordon node
   Client Agent → Kubernetes: Evict all pods (gracefully)
   Client Agent → Central Server: POST /api/v1/client/tasks/task-789/result

8. Central Server records event
   Central Server → Database: INSERT INTO spot_events (...)
   Central Server → Admin Frontend: WebSocket update (Spot event handled)
```

---

## 📝 Error Handling Standards

### HTTP Status Codes
```
200 OK - Request successful
201 Created - Resource created
400 Bad Request - Invalid input
401 Unauthorized - Invalid API key
403 Forbidden - Insufficient permissions
404 Not Found - Resource not found
409 Conflict - Resource conflict (e.g., duplicate)
422 Unprocessable Entity - Validation error
429 Too Many Requests - Rate limit exceeded
500 Internal Server Error - Server error
503 Service Unavailable - Service down
```

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid cluster_id provided",
    "details": {
      "field": "cluster_id",
      "constraint": "must be valid UUID"
    },
    "request_id": "req-12345",
    "timestamp": "2025-11-28T10:00:00Z"
  }
}
```

### Retry Logic
```python
# common/utils/retry.py
import asyncio
from typing import Callable, Any

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
):
    """Retry function with exponential backoff"""
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            await asyncio.sleep(delay)
            delay *= backoff_factor
```

---

## 🎯 Integration Checklist

### ML Server ↔ Central Server
- [ ] Central Server has ML Server URL configured
- [ ] Central Server has ML Server API key
- [ ] ML Server validates Central Server requests
- [ ] Common schemas aligned (DecisionRequest, DecisionResponse)
- [ ] Error handling implemented
- [ ] Timeout handling configured
- [ ] Health check endpoint tested

### Central Server ↔ Client Agent
- [ ] Client Agent has Central Server URL
- [ ] Client Agent has valid API key (in Secret)
- [ ] Central Server validates Client requests
- [ ] Task polling working
- [ ] Metrics submission working
- [ ] WebSocket connection stable
- [ ] Common schemas aligned (Task, TaskResult, ClusterMetrics)

### Central Server ↔ Database
- [ ] Database schema created
- [ ] Migrations applied
- [ ] Central Server connection pool configured
- [ ] ML Server read-only access configured
- [ ] Indexes created for performance
- [ ] Backup strategy implemented

### Central Server ↔ Admin Frontend
- [ ] Frontend has API URL configured
- [ ] CORS configured correctly
- [ ] WebSocket connection working
- [ ] Real-time updates flowing
- [ ] Authentication working

---

**END OF INTEGRATION GUIDE**
*Update this document when adding new integration points or changing schemas*
