# Client Server - Session Memory & Documentation

## 📋 Overview
**Component**: Client Server (Client-Side Agent)
**Purpose**: Lightweight agent that runs tasks delegated by Central Server on customer's Kubernetes cluster
**Instance Type**: Runs as Deployment/Pod inside customer's Kubernetes cluster
**Created**: 2025-11-28
**Last Updated**: 2025-11-28

---

## 🎯 Core Responsibilities

### 1. Task Execution
- Polls Central Server for pending tasks
- Executes tasks on local Kubernetes cluster:
  - Node draining (graceful pod eviction)
  - Label updates on nodes/pods
  - Pod rescheduling
  - Node cordon/uncordon
- Reports task execution results back to Central Server

### 2. Metrics Collection
- Collects cluster metrics:
  - Node resource usage (CPU, memory)
  - Pod resource requests/limits
  - Spot vs On-Demand node counts
  - Current cluster cost (calculated)
- Sends metrics to Central Server periodically

### 3. Event Monitoring
- Watches Kubernetes events:
  - Pod scheduling failures
  - Node NotReady conditions
  - Pod evictions
  - OOMKilled events
- Forwards relevant events to Central Server

### 4. Health Reporting
- Reports agent health status
- Monitors Kubernetes API connectivity
- Sends heartbeat to Central Server

---

## 🔌 Integration Points (Common Components)

### A. Communication with Central Server
**Protocol**: REST API (Client → Central) + WebSocket (for real-time tasks)
**Direction**: Client polls Central, Central pushes urgent tasks via WebSocket

**Endpoints Called on Central Server**:
- `GET /api/v1/client/tasks?cluster_id={id}` - Poll for pending tasks
- `POST /api/v1/client/tasks/{task_id}/result` - Report task execution result
- `POST /api/v1/client/metrics` - Send cluster metrics
- `POST /api/v1/client/events` - Send cluster events
- `POST /api/v1/client/heartbeat` - Health check heartbeat
- `WS /api/v1/client/stream` - WebSocket for real-time task streaming

**Polling Frequency**:
- Tasks: Every 10 seconds
- Metrics: Every 60 seconds
- Heartbeat: Every 30 seconds

**Data Flow**:
```
Client Agent → Central Server: GET /client/tasks (poll)
Central Server → Client Agent: [{task1}, {task2}]
Client Agent: Execute tasks on Kubernetes cluster
Client Agent → Central Server: POST /tasks/{id}/result (status, logs)
```

### B. Kubernetes API Interaction
**Client Library**: `kubernetes` Python client
**Authentication**: ServiceAccount token (mounted in pod)
**Permissions Required**:
```yaml
# RBAC ClusterRole
rules:
  # Read permissions
  - apiGroups: [""]
    resources: ["nodes", "pods", "events"]
    verbs: ["get", "list", "watch"]

  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets", "daemonsets"]
    verbs: ["get", "list"]

  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]

  # Write permissions (limited)
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["patch"]  # For labels, cordon/uncordon

  - apiGroups: [""]
    resources: ["pods/eviction"]
    verbs: ["create"]  # For draining nodes
```

### C. Shared Data Schemas (COMMON)
**Location**: `/common/schemas/` (shared across all servers)

```python
# Task schema (received from Central Server)
class Task(BaseModel):
    task_id: str
    cluster_id: str
    task_type: str  # drain_node, label_node, cordon_node, etc.
    parameters: Dict[str, Any]
    priority: int  # 1=highest, 10=lowest
    deadline: datetime
    created_at: datetime

# Task result (sent to Central Server)
class TaskResult(BaseModel):
    task_id: str
    status: str  # success, failed, timeout
    logs: str
    executed_at: datetime
    duration_seconds: float
    error: Optional[str]

# Metrics data
class ClusterMetrics(BaseModel):
    cluster_id: str
    timestamp: datetime
    node_count: int
    spot_node_count: int
    on_demand_node_count: int
    total_cpu_cores: float
    total_memory_gb: float
    allocated_cpu_cores: float
    allocated_memory_gb: float
    pod_count: int
    current_cost_per_hour: float
```

### D. Configuration
**Location**: ConfigMap in Kubernetes
**Contents**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cloudoptim-client-config
  namespace: kube-system
data:
  central-server-url: "https://central.cloudoptim.io"
  cluster-id: "cluster-123"
  poll-interval-seconds: "10"
  metrics-interval-seconds: "60"
  log-level: "INFO"
```

**Secrets**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cloudoptim-client-secret
  namespace: kube-system
type: Opaque
data:
  api-key: <base64-encoded-api-key>
```

---

## 📁 Directory Structure

```
client-server/
├── SESSION_MEMORY.md          # This file
├── README.md
├── requirements.txt
├── Dockerfile                  # Container image
├── deployment.yaml             # Kubernetes Deployment manifest
├── config/
│   ├── common.yaml            # Shared config
│   └── client_config.yaml     # Client-specific config
├── agent/
│   ├── main.py                # Agent entry point
│   ├── task_executor.py       # Executes tasks
│   ├── metrics_collector.py   # Collects metrics
│   ├── event_watcher.py       # Watches K8s events
│   ├── central_client.py      # Central Server API client
│   ├── k8s_client.py          # Kubernetes API wrapper
│   └── health_check.py        # Health monitoring
├── tasks/
│   ├── drain_node.py          # Node draining logic
│   ├── label_node.py          # Label update logic
│   ├── cordon_node.py         # Cordon/uncordon logic
│   └── pod_operations.py      # Pod-level operations
├── scripts/
│   ├── install.sh             # Installation script
│   └── uninstall.sh           # Cleanup script
├── tests/
│   ├── test_tasks.py
│   └── test_metrics.py
└── docs/
    └── DEPLOYMENT.md
```

---

## 🔧 Technology Stack

### Core
- **Language**: Python 3.10+
- **Async Framework**: asyncio
- **HTTP Client**: httpx (async)
- **WebSocket**: websockets library

### Kubernetes
- **Client Library**: kubernetes-client 27.2.0
- **Metrics API**: Custom objects API for metrics.k8s.io

### Monitoring
- **Logging**: python-json-logger (structured logs)
- **Health Checks**: Built-in HTTP endpoint

### Deployment
- **Container**: Docker (minimal Python image)
- **Orchestration**: Deployed as Kubernetes Deployment

---

## 🚀 Deployment Configuration

### Environment Variables (from ConfigMap/Secret)
```bash
# Central Server
CENTRAL_SERVER_URL=https://central.cloudoptim.io
CENTRAL_API_KEY=xxx  # from Secret

# Cluster Identity
CLUSTER_ID=cluster-123

# Polling Configuration
TASK_POLL_INTERVAL_SECONDS=10
METRICS_POLL_INTERVAL_SECONDS=60
HEARTBEAT_INTERVAL_SECONDS=30

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Health Check
HEALTH_CHECK_PORT=8080
```

### Kubernetes Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudoptim-agent
  namespace: kube-system
  labels:
    app: cloudoptim-agent
spec:
  replicas: 1  # Single agent per cluster
  selector:
    matchLabels:
      app: cloudoptim-agent
  template:
    metadata:
      labels:
        app: cloudoptim-agent
    spec:
      serviceAccountName: cloudoptim-agent
      containers:
      - name: agent
        image: cloudoptim/client-agent:latest
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
        env:
        - name: CENTRAL_SERVER_URL
          valueFrom:
            configMapKeyRef:
              name: cloudoptim-client-config
              key: central-server-url
        - name: CLUSTER_ID
          valueFrom:
            configMapKeyRef:
              name: cloudoptim-client-config
              key: cluster-id
        - name: CENTRAL_API_KEY
          valueFrom:
            secretKeyRef:
              name: cloudoptim-client-secret
              key: api-key
        ports:
        - name: health
          containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
```

### RBAC Configuration
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cloudoptim-agent
  namespace: kube-system

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cloudoptim-agent
rules:
  # Read nodes and pods
  - apiGroups: [""]
    resources: ["nodes", "pods", "events", "namespaces"]
    verbs: ["get", "list", "watch"]

  # Read workloads
  - apiGroups: ["apps"]
    resources: ["deployments", "statefulsets", "daemonsets", "replicasets"]
    verbs: ["get", "list", "watch"]

  # Read metrics
  - apiGroups: ["metrics.k8s.io"]
    resources: ["nodes", "pods"]
    verbs: ["get", "list"]

  # Modify nodes (labels, cordon)
  - apiGroups: [""]
    resources: ["nodes"]
    verbs: ["patch", "update"]

  # Evict pods (for draining)
  - apiGroups: [""]
    resources: ["pods/eviction"]
    verbs: ["create"]

  # Read PodDisruptionBudgets
  - apiGroups: ["policy"]
    resources: ["poddisruptionbudgets"]
    verbs: ["get", "list"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cloudoptim-agent
subjects:
- kind: ServiceAccount
  name: cloudoptim-agent
  namespace: kube-system
roleRef:
  kind: ClusterRole
  name: cloudoptim-agent
  apiGroup: rbac.authorization.k8s.io
```

---

## 🔄 Core Workflows

### 1. Task Polling Loop
```python
async def task_polling_loop():
    while True:
        try:
            # Poll Central Server for tasks
            tasks = await central_client.get_tasks(cluster_id)

            for task in tasks:
                # Execute task based on type
                result = await execute_task(task)

                # Report result back
                await central_client.report_task_result(
                    task_id=task.task_id,
                    result=result
                )

        except Exception as e:
            logger.error(f"Error in task polling: {e}")

        await asyncio.sleep(TASK_POLL_INTERVAL_SECONDS)
```

### 2. Metrics Collection Loop
```python
async def metrics_collection_loop():
    while True:
        try:
            # Collect cluster metrics
            metrics = await collect_cluster_metrics()

            # Send to Central Server
            await central_client.send_metrics(metrics)

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")

        await asyncio.sleep(METRICS_POLL_INTERVAL_SECONDS)
```

### 3. Node Draining Task
```python
async def drain_node(node_name: str, grace_period: int = 90):
    """
    Gracefully drain a node by evicting all pods
    """
    # Step 1: Cordon the node
    await k8s_client.cordon_node(node_name)

    # Step 2: Get all pods on the node
    pods = await k8s_client.list_pods_on_node(node_name)

    # Step 3: Evict pods one by one
    for pod in pods:
        # Skip system pods
        if pod.namespace in ['kube-system', 'kube-public']:
            continue

        # Check PodDisruptionBudget
        pdb = await k8s_client.get_pdb_for_pod(pod)
        if pdb and pdb.status.disruptionsAllowed == 0:
            logger.warning(f"Cannot evict {pod.name}: PDB prevents eviction")
            continue

        # Evict pod
        await k8s_client.evict_pod(
            name=pod.name,
            namespace=pod.namespace,
            grace_period_seconds=grace_period
        )

        # Wait between evictions
        await asyncio.sleep(10)

    # Step 4: Verify node is empty
    remaining_pods = await k8s_client.list_pods_on_node(node_name)

    if len(remaining_pods) > 0:
        return TaskResult(
            status='failed',
            logs=f'Node still has {len(remaining_pods)} pods',
            error='Drain incomplete'
        )

    return TaskResult(
        status='success',
        logs=f'Successfully drained {len(pods)} pods'
    )
```

---

## 🔗 Common Components Shared Across Servers

### 1. Task Schema
**Location**: `/common/schemas/tasks.py`
**Defined By**: Central Server
**Used By**: Client Agent receives and executes

**Task Types**:
- `drain_node`: Gracefully evict all pods from a node
- `cordon_node`: Mark node as unschedulable
- `uncordon_node`: Mark node as schedulable
- `label_node`: Add/update labels on a node
- `delete_pod`: Delete a specific pod

### 2. Metrics Schema
**Location**: `/common/schemas/metrics.py`
**Defined By**: Central Server
**Populated By**: Client Agent

### 3. Authentication
**Method**: API Key (Bearer token)
**Header**: `Authorization: Bearer {API_KEY}`
**Validation**: Central Server validates all requests

### 4. Logging Format
**Format**: JSON (structured logging)
**Fields**:
```json
{
  "timestamp": "2025-11-28T10:00:00Z",
  "level": "INFO",
  "cluster_id": "cluster-123",
  "component": "task_executor",
  "message": "Successfully drained node",
  "task_id": "task-456",
  "node_name": "ip-10-0-1-23",
  "duration_seconds": 45.2
}
```

---

## 📊 Metrics Collected

### Node Metrics
- Total node count
- Spot node count
- On-Demand node count
- Node status (Ready, NotReady)
- Instance types and AZs

### Resource Metrics
- Total CPU cores (allocatable)
- Total memory GB (allocatable)
- Allocated CPU cores (requests)
- Allocated memory GB (requests)
- CPU/memory utilization percentage

### Pod Metrics
- Total pod count
- Running pods
- Pending pods
- Failed pods

### Cost Metrics (Calculated)
- Current cost per hour (based on instance types)
- Spot vs On-Demand cost breakdown

---

## 🔄 Session Updates Log

### 2025-11-28 - Initial Setup
**Changes Made**:
- Created client-server folder structure
- Documented agent responsibilities
- Defined integration with Central Server
- Specified Kubernetes RBAC requirements
- Documented task execution workflows
- Listed common components and schemas

**Next Steps**:
1. Implement task executor logic
2. Create metrics collector
3. Implement Kubernetes API wrapper
4. Create Central Server API client
5. Build Docker image
6. Create installation script
7. Write comprehensive tests

---

## 📝 Agent Operations

### Startup Sequence
1. Load configuration from ConfigMap
2. Initialize Kubernetes client (in-cluster config)
3. Validate connection to Central Server
4. Register cluster with Central Server
5. Start task polling loop
6. Start metrics collection loop
7. Start event watcher
8. Start health check HTTP server

### Shutdown Sequence
1. Stop accepting new tasks
2. Complete in-progress tasks (with timeout)
3. Send final metrics snapshot
4. Deregister from Central Server
5. Clean exit

### Error Handling
- **Network errors**: Retry with exponential backoff
- **Task failures**: Report to Central Server with error details
- **Kubernetes API errors**: Log and continue (don't crash)
- **Authentication errors**: Alert and exit (requires manual fix)

---

## 🐛 Troubleshooting

### Agent Not Polling Tasks
**Symptom**: No task execution
**Solution**: Check CENTRAL_SERVER_URL, verify API key, check network connectivity

### Cannot Drain Nodes
**Symptom**: "Forbidden" errors
**Solution**: Verify RBAC permissions, check ServiceAccount configuration

### Metrics Not Showing in Dashboard
**Symptom**: No data in Central Server
**Solution**: Check metrics collection loop, verify API endpoint, check logs

### High Memory Usage
**Symptom**: Agent pod OOMKilled
**Solution**: Increase memory limits, check for memory leaks

---

## 📌 Important Notes

1. **Lightweight**: Minimal resource footprint (100m CPU, 128Mi RAM)
2. **Single Replica**: Only one agent per cluster (no need for multiple)
3. **Read-Mostly**: Mostly reads Kubernetes state, limited writes
4. **Stateless**: No local state, all state in Central Server
5. **Resilient**: Handles network failures, Kubernetes API unavailability
6. **Non-Intrusive**: Does not modify application workloads, only infrastructure

---

## 🎯 Integration Checklist

- [ ] ConfigMap created with Central Server URL
- [ ] Secret created with API key
- [ ] ServiceAccount created
- [ ] ClusterRole and ClusterRoleBinding configured
- [ ] Deployment manifest applied
- [ ] Agent pod running and healthy
- [ ] Task polling working
- [ ] Metrics collection working
- [ ] Event watching working
- [ ] Health check endpoint responding

---

## ⚠️ Security Considerations

1. **Minimal Permissions**: Only required RBAC permissions granted
2. **No Secret Access**: Cannot read Secrets (except its own API key)
3. **No ConfigMap Write**: Cannot modify cluster configuration
4. **Namespace Isolation**: Runs in kube-system, isolated from apps
5. **API Key Rotation**: Support for API key rotation without downtime
6. **TLS**: All communication with Central Server over HTTPS

---

## 🔍 Monitoring & Observability

### Health Endpoints
```
GET /health
Response: {"status": "healthy", "uptime_seconds": 3600}

GET /ready
Response: {"ready": true, "central_server_connected": true, "k8s_api_connected": true}

GET /metrics
Response: Prometheus-format metrics (optional)
```

### Key Metrics to Monitor
- Task execution success rate
- Task execution duration
- Metrics collection success rate
- Central Server connection status
- Kubernetes API connection status

---

**END OF SESSION MEMORY - CLIENT SERVER**
*Append all future changes and updates below this line*

---
