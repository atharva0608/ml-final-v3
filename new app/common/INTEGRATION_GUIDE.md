# Common Components & Integration Guide
## CloudOptim - Agentless Architecture Integration Documentation

**Created**: 2025-11-28
**Last Updated**: 2025-11-28
**Architecture**: Agentless (EventBridge + SQS + Remote Kubernetes API)

---

## 📋 Overview

This document defines all common components, data schemas, APIs, and integration patterns for the CloudOptim agentless Kubernetes cost optimization platform.

**Two-Server Architecture**:
1. **ML Server** - Machine Learning & Decision Engine (inference-only)
2. **Core Platform** - Backend, Database, Admin Frontend, Remote K8s API client

**No Client-Side Agents**: All cluster operations via remote Kubernetes API

---

## 🏗️ System Architecture

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
│           │ Remote K8s API            │ SQS polling           │
│           │ (HTTPS)                   │                       │
└───────────┼───────────────────────────┼───────────────────────┘
            │                           │
            │                           │
    ┌───────┴───────────────────────────┴───────┐
    │                                            │
    │  CloudOptim Control Plane                 │
    │                                            │
    │  ┌──────────────────────────────────────┐ │
    │  │     Core Platform (Port 8000)       │ │
    │  │  • FastAPI REST API                 │ │
    │  │  • PostgreSQL Database              │ │
    │  │  • Admin Frontend (React)           │ │
    │  │  • EventBridge/SQS Poller           │ │
    │  │  • Remote K8s API Client            │ │
    │  │  • AWS EC2 API Client               │ │
    │  └──────────────┬───────────────────────┘ │
    │                 │ REST API                 │
    │  ┌──────────────┴───────────────────────┐ │
    │  │     ML Server (Port 8001)            │ │
    │  │  • Model Hosting (inference-only)   │ │
    │  │  • Decision Engines (pluggable)     │ │
    │  │  • Data Gap Filler                  │ │
    │  │  • Spot Advisor Cache (Redis)       │ │
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

## 🔗 Integration Patterns (Agentless)

### Pattern 1: Request-Response (Synchronous)
**Used For**: ML predictions, decision requests
**Flow**:
```
Core Platform → ML Server: POST /api/v1/ml/decision/spot-optimize
ML Server: Process request, run decision engine
ML Server → Core Platform: JSON response with recommendations
Core Platform: Execute via remote K8s API + AWS EC2 API
```

### Pattern 2: Event-Driven (EventBridge + SQS)
**Used For**: Spot interruption warnings
**Flow**:
```
AWS EC2 → EventBridge: Spot interruption warning (2-min notice)
EventBridge → Customer SQS Queue: Forward event
Core Platform → SQS Queue: Poll every 5 seconds
Core Platform: Receive warning, process event
Core Platform → Remote K8s API: Drain node
Core Platform → AWS EC2 API: Launch replacement
```

### Pattern 3: Scheduled Polling (Remote K8s API)
**Used For**: Cluster metrics collection
**Flow**:
```
Core Platform → Remote K8s API: GET /api/v1/nodes (every 30s)
Core Platform → Remote K8s API: GET /apis/metrics.k8s.io/v1beta1/nodes
Core Platform: Store metrics in PostgreSQL
Core Platform → ML Server: Send cluster state for optimization
```

### Pattern 4: On-Demand Remote Operations
**Used For**: Optimization execution
**Flow**:
```
Core Platform → ML Server: Request optimization decision
ML Server → Core Platform: Return execution plan
Core Platform → Remote K8s API: Drain nodes, cordon nodes
Core Platform → AWS EC2 API: Launch/terminate instances
Core Platform → Database: Record optimization results
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
├── k8s_models.py      # Kubernetes resource schemas
└── aws_models.py      # AWS event schemas
```

### Core Models

#### 1. ClusterState
**Purpose**: Represents current state of a Kubernetes cluster
**Used By**: Core Platform → ML Server communication
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
**Purpose**: Request sent from Core Platform to ML Server for optimization decisions
**Flow**: Core Platform → ML Server
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
**Flow**: ML Server → Core Platform
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

#### 4. RemoteK8sTask
**Purpose**: Task for remote Kubernetes API operations
**Flow**: Core Platform → Remote K8s API
**Definition**:
```python
class RemoteK8sTask(BaseModel):
    task_id: str
    cluster_id: str
    task_type: str  # drain_node, cordon_node, scale_deployment

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
**Purpose**: Result of task execution
**Flow**: Core Platform internal (after remote K8s API call)
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
**Purpose**: Metrics collected from remote Kubernetes API
**Flow**: Remote K8s API → Core Platform
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
**Purpose**: Spot instance interruption event from AWS EventBridge
**Flow**: AWS EventBridge → SQS → Core Platform
**Definition**:
```python
class SpotEvent(BaseModel):
    event_id: str
    cluster_id: str
    instance_id: str
    event_type: str  # interruption_warning, terminated
    event_time: datetime
    received_at: datetime

    # Event details
    detail: dict  # Raw AWS event detail

    # Action taken
    action_taken: Optional[str]
    replacement_instance_id: Optional[str]
    drain_duration_seconds: Optional[int]
    processed_at: Optional[datetime]
```

#### 8. AWS EC2 Models
**Purpose**: AWS EC2 instance operations
**Definition**:
```python
class EC2InstanceLaunchRequest(BaseModel):
    instance_type: str
    availability_zone: str
    instance_market: str  # spot, on-demand
    tags: dict
    user_data: Optional[str]

class EC2InstanceTerminateRequest(BaseModel):
    instance_id: str
    reason: str  # optimization, interruption, manual

class SpotPriceQuery(BaseModel):
    instance_types: List[str]
    regions: List[str]
    start_time: datetime
    end_time: datetime
```

---

## 🔗 API Endpoints

### ML Server (Port 8001)

#### Model Management
```http
POST /api/v1/ml/models/upload
  → Upload pre-trained model
  → Body: multipart/form-data with .pkl file
  → Returns: {model_id, name, version, trained_until}

GET /api/v1/ml/models/list
  → List all uploaded models
  → Returns: [{model_id, name, version, trained_until, active}]

POST /api/v1/ml/models/activate
  → Activate model version
  → Body: {model_id, version}
  → Returns: {status, activated_at}
```

#### Decision Engines
```http
POST /api/v1/ml/engines/upload
  → Upload decision engine module
  → Body: multipart/form-data with .py file
  → Returns: {engine_id, name, version}

GET /api/v1/ml/engines/list
  → List available engines
  → Returns: [{engine_id, name, version, active}]

POST /api/v1/ml/engines/select
  → Select active engine
  → Body: {engine_id, config}
  → Returns: {status, activated_at}
```

#### Gap Filling
```http
POST /api/v1/ml/gap-filler/analyze
  → Analyze data gaps
  → Body: {model_id}
  → Returns: {trained_until, current_date, gap_days}

POST /api/v1/ml/gap-filler/fill
  → Fill gaps with AWS data
  → Body: {model_id, instance_types, regions}
  → Returns: {task_id, status}

GET /api/v1/ml/gap-filler/status/{task_id}
  → Check gap-filling progress
  → Returns: {status, percent_complete, eta_seconds}
```

#### Predictions & Decisions
```http
POST /api/v1/ml/predict/spot-interruption
  → Predict Spot interruption probability
  → Body: {instance_type, region, spot_price, launch_time}
  → Returns: {interruption_probability, confidence}

POST /api/v1/ml/decision/spot-optimize
  → Get Spot optimization recommendations
  → Body: DecisionRequest (see schema above)
  → Returns: DecisionResponse (see schema above)

POST /api/v1/ml/decision/bin-pack
  → Get bin packing recommendations
  → Body: DecisionRequest
  → Returns: DecisionResponse

POST /api/v1/ml/decision/rightsize
  → Get rightsizing recommendations
  → Body: DecisionRequest
  → Returns: DecisionResponse
```

### Core Platform (Port 8000)

#### Customer & Cluster Management
```http
GET /api/v1/admin/clusters
  → List all clusters
  → Returns: [{cluster_id, name, region, status, cost}]

POST /api/v1/admin/clusters
  → Register new cluster
  → Body: {name, k8s_api_endpoint, k8s_token, aws_role_arn, sqs_queue_url}
  → Returns: {cluster_id, status}

GET /api/v1/admin/clusters/{id}
  → Get cluster details
  → Returns: {cluster_id, details, metrics, savings}

GET /api/v1/admin/savings
  → Get real-time savings
  → Returns: {total_savings, breakdown_by_cluster}
```

#### Optimization
```http
POST /api/v1/optimization/trigger
  → Trigger optimization
  → Body: {cluster_id, optimization_type}
  → Returns: {optimization_id, status}

GET /api/v1/optimization/history
  → Get optimization history
  → Query params: cluster_id, limit, offset
  → Returns: [{optimization_id, type, savings, timestamp}]
```

#### EventBridge Integration
```http
GET /api/v1/events/spot-warnings
  → Get recent Spot warnings
  → Query params: cluster_id, since
  → Returns: [{event_id, instance_id, event_time, action_taken}]

POST /api/v1/events/process
  → Manually process Spot event
  → Body: {event_id}
  → Returns: {status, action_taken}
```

#### Remote Kubernetes Operations (Agentless)
```http
GET /api/v1/k8s/{cluster_id}/nodes
  → List cluster nodes (via remote K8s API)
  → Returns: [{node_name, instance_id, status, cpu, memory}]

GET /api/v1/k8s/{cluster_id}/pods
  → List cluster pods (via remote K8s API)
  → Returns: [{pod_name, namespace, node, status}]

GET /api/v1/k8s/{cluster_id}/metrics
  → Get cluster metrics (via remote K8s API)
  → Returns: ClusterMetrics (see schema)

POST /api/v1/k8s/{cluster_id}/nodes/drain
  → Drain node remotely
  → Body: {node_name, grace_period}
  → Returns: {task_id, status}

POST /api/v1/k8s/{cluster_id}/nodes/cordon
  → Cordon node remotely
  → Body: {node_name}
  → Returns: {status}

POST /api/v1/k8s/{cluster_id}/scale
  → Scale deployment remotely
  → Body: {deployment_name, namespace, replicas}
  → Returns: {status}
```

#### Ghost Probe Scanner
```http
POST /api/v1/scanner/scan
  → Scan for ghost instances
  → Body: {customer_id}
  → Returns: {scan_id, ghosts_found}

GET /api/v1/scanner/ghosts
  → List detected ghost instances
  → Returns: [{instance_id, detected_at, status}]

POST /api/v1/scanner/terminate/{id}
  → Terminate ghost instance
  → Returns: {status, terminated_at}
```

---

## 🔧 Authentication

### API Key Authentication
**Used For**: Core Platform ↔ ML Server
**Header**: `X-API-Key: <api_key>`

### Service Account Token
**Used For**: Core Platform → Remote Kubernetes API
**Header**: `Authorization: Bearer <service_account_token>`

### AWS IAM Role
**Used For**: Core Platform → AWS APIs (EC2, SQS)
**Method**: Cross-account IAM role assumption

---

## 📁 Common Directory Structure

```
common/
├── INTEGRATION_GUIDE.md   # This file
├── schemas/
│   ├── __init__.py
│   ├── models.py          # Core Pydantic models
│   ├── requests.py        # API request schemas
│   ├── responses.py       # API response schemas
│   ├── k8s_models.py      # Kubernetes models
│   └── aws_models.py      # AWS event models
├── auth/
│   ├── __init__.py
│   ├── api_key.py         # API key authentication
│   └── k8s_token.py       # K8s service account token handling
├── config/
│   ├── __init__.py
│   ├── common.yaml        # Shared config
│   └── constants.py       # Common constants
└── utils/
    ├── __init__.py
    ├── logging.py         # Structured logging
    ├── retry.py           # Retry logic
    └── validation.py      # Common validation
```

---

## 🔄 Data Flow Examples

### Example 1: Spot Optimization (End-to-End)

```
1. Core Platform → Remote K8s API: GET /api/v1/nodes
   → Returns: List of nodes with metrics

2. Core Platform → ML Server: POST /api/v1/ml/decision/spot-optimize
   → Body: DecisionRequest with current cluster state

3. ML Server: Analyze cluster, run Spot optimizer decision engine
   → Uses AWS Spot Advisor public data
   → Calculates risk scores

4. ML Server → Core Platform: DecisionResponse
   → Returns: Recommendations with execution plan

5. Core Platform: Validate recommendations, check safety constraints

6. Core Platform → AWS EC2 API: RunInstances
   → Launch new Spot instances per recommendations

7. New instances join cluster (kubelet self-registers)

8. Core Platform → Remote K8s API: POST /api/v1/namespaces/.../pods/.../eviction
   → Drain old nodes

9. Core Platform → AWS EC2 API: TerminateInstances
   → Terminate old instances

10. Core Platform → Database: Record optimization, calculate savings
```

### Example 2: Spot Interruption Handling (Real-Time)

```
1. AWS EC2: Spot instance i-1234 will terminate in 2 minutes

2. AWS → EventBridge: Spot interruption warning event

3. EventBridge → Customer SQS Queue: Forward event

4. Core Platform (SQS Poller): Poll queue every 5 seconds
   → Receive event

5. Core Platform: Parse event, identify cluster and node

6. Core Platform → Remote K8s API: POST /api/v1/namespaces/.../pods/.../eviction
   → Drain node (evict all pods with grace period)

7. Core Platform → AWS EC2 API: RunInstances
   → Launch replacement instance

8. Core Platform: Monitor drain progress via Remote K8s API

9. New instance joins cluster, workloads rescheduled

10. Core Platform → AWS EC2 API: TerminateInstances
    → Terminate interrupted instance (optional, will auto-terminate)

11. Core Platform → Database: Record Spot event, action taken
```

### Example 3: Ghost Probe Scanner

```
1. Core Platform (Scheduler): Trigger scan every 6 hours

2. Core Platform → AWS EC2 API: DescribeInstances
   → Get all running EC2 instances in customer account

3. Core Platform → Remote K8s API: GET /api/v1/nodes
   → Get all Kubernetes nodes

4. Core Platform: Compare EC2 instances vs K8s nodes
   → Identify instances running but NOT in K8s (ghost instances)

5. Core Platform → Database: Store ghost instances
   → Status: detected, detected_at: now

6. After 24-hour grace period:
   Core Platform → AWS EC2 API: TerminateInstances
   → Terminate ghost instances

7. Core Platform → Webhook: Notify customer
   → Send Slack/email notification

8. Core Platform → Database: Update ghost instance status
   → Status: terminated, terminated_at: now
```

---

## 🛡️ Error Handling Standards

### HTTP Status Codes
- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

### Error Response Format
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Instance type 'm5.invalidsize' is not valid",
    "details": {
      "field": "instance_type",
      "valid_values": ["m5.large", "m5.xlarge", ...]
    },
    "timestamp": "2025-11-28T10:00:00Z",
    "request_id": "req-12345"
  }
}
```

### Retry Strategy
```python
# For remote K8s API calls
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # Exponential backoff
TIMEOUT = 30  # seconds

# For SQS polling
VISIBILITY_TIMEOUT = 30  # seconds
WAIT_TIME = 20  # Long polling

# For AWS EC2 API calls
MAX_RETRIES = 5
BACKOFF_FACTOR = 1.5
```

---

## 📌 Important Notes

1. **Agentless Architecture**: NO client-side components, all operations via remote APIs
2. **Remote K8s API**: Service account token required, RBAC permissions must be configured
3. **EventBridge + SQS**: Customer must set up in their AWS account for Spot warnings
4. **Public Data First**: AWS Spot Advisor provides Day Zero recommendations
5. **Security**: All tokens/credentials encrypted at rest, TLS for all communication

---

## 🎯 Customer Onboarding Checklist

### AWS Setup
- [ ] Create IAM role with CloudOptim trust policy
- [ ] Attach required EC2 + SQS permissions
- [ ] Create EventBridge rule for Spot interruptions
- [ ] Create SQS queue: `cloudoptim-spot-warnings-{customer_id}`
- [ ] Configure EventBridge to target SQS queue

### Kubernetes Setup
- [ ] Create service account: `cloudoptim` in `kube-system`
- [ ] Create ClusterRole with required permissions
- [ ] Create ClusterRoleBinding
- [ ] Generate service account token
- [ ] Verify remote API access (test connection)

### CloudOptim Setup
- [ ] Register cluster in Core Platform
- [ ] Provide K8s API endpoint + service account token
- [ ] Provide AWS IAM Role ARN + SQS Queue URL
- [ ] Verify EventBridge/SQS integration
- [ ] Run initial optimization
- [ ] Monitor for 24 hours

---

**END OF INTEGRATION GUIDE - AGENTLESS ARCHITECTURE**
