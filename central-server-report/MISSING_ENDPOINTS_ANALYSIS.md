# Missing & Recommended API Endpoints

**Analysis Date:** 2025-11-26
**Purpose:** Identify endpoints that should be created in the backend to support frontend functionality

---

## Executive Summary

Currently, the frontend has **5 mock methods** that return empty/placeholder data because the backend endpoints don't exist. Additionally, there are **7 recommended endpoints** that would improve functionality based on the user's frontend requirements.

**Total Missing/Recommended:** 12 endpoints

---

## 1. Currently Mock Methods (Need Backend Implementation)

These methods exist in `frontend/src/services/apiClient.jsx` but return mock data:

### 1.1 Global Search
**Frontend Method:** `globalSearch(query)`
**Current Behavior:** Returns `{ clients: [], instances: [], agents: [] }`
**Recommended Backend Endpoint:** `GET /api/admin/search?q={query}`

**Purpose:** Search across all clients, instances, and agents
**Request:**
```
GET /api/admin/search?q=i-123456&types=clients,instances,agents
```

**Response:**
```json
{
  "query": "i-123456",
  "results": {
    "clients": [
      {
        "id": "client_uuid",
        "name": "Client A",
        "email": "client@example.com",
        "matchField": "name"
      }
    ],
    "instances": [
      {
        "id": "i-1234567890abcdef0",
        "client_id": "client_uuid",
        "client_name": "Client A",
        "instance_type": "t3.medium",
        "status": "running_primary"
      }
    ],
    "agents": [
      {
        "id": "agent_uuid",
        "client_id": "client_uuid",
        "client_name": "Client A",
        "hostname": "ip-10-0-1-100",
        "status": "online"
      }
    ]
  },
  "total_results": 3
}
```

**Usage:** SearchResultsPanel component
**Priority:** Medium (improves admin UX)

---

### 1.2 Agent Statistics
**Frontend Method:** `getAgentStatistics(agentId)`
**Current Behavior:** Returns `{ totalDecisions: 0, successRate: 0 }`
**Recommended Backend Endpoint:** `GET /api/agents/{agent_id}/statistics`

**Purpose:** Get decision engine statistics for an agent
**Response:**
```json
{
  "agent_id": "agent_uuid",
  "statistics": {
    "total_decisions": 145,
    "switches_executed": 38,
    "switches_recommended": 45,
    "success_rate": 0.95,
    "average_confidence": 0.82,
    "last_decision_at": "2024-11-26T10:00:00Z",
    "decisions_by_trigger": {
      "automatic": 35,
      "manual": 3
    },
    "avg_downtime_seconds": 12,
    "total_savings_generated": 45.60
  }
}
```

**Usage:** Agent detail view, analytics
**Priority:** High (provides valuable insights)

---

### 1.3 Instance Logs
**Frontend Method:** `getInstanceLogs(instanceId, limit)`
**Current Behavior:** Returns `[]`
**Recommended Backend Endpoint:** `GET /api/client/instances/{instance_id}/logs?limit={limit}`

**Purpose:** Get lifecycle event logs for an instance
**Response:**
```json
[
  {
    "timestamp": "2024-11-26T10:00:00Z",
    "event_type": "switch_initiated",
    "message": "Switch initiated to pool us-east-1b-pool-2",
    "severity": "info",
    "metadata": {
      "from_pool": "us-east-1a-pool-1",
      "to_pool": "us-east-1b-pool-2",
      "trigger": "automatic"
    }
  },
  {
    "timestamp": "2024-11-26T10:04:12Z",
    "event_type": "switch_completed",
    "message": "Switch completed successfully",
    "severity": "success",
    "metadata": {
      "downtime_seconds": 12,
      "new_instance_id": "i-new-456"
    }
  },
  {
    "timestamp": "2024-11-26T09:00:00Z",
    "event_type": "termination_notice",
    "message": "AWS rebalance recommendation received",
    "severity": "warning",
    "metadata": {
      "notice_type": "rebalance_recommendation",
      "action_taken": "emergency_replica_created"
    }
  }
]
```

**Usage:** Instance detail panel, debugging
**Priority:** High (critical for troubleshooting)

---

### 1.4 Pool Statistics
**Frontend Method:** `getPoolStatistics()`
**Current Behavior:** Returns `{ total: 0, active: 0, regions: [] }`
**Recommended Backend Endpoint:** `GET /api/admin/pools/statistics`

**Purpose:** Get statistics about spot pools
**Response:**
```json
{
  "total_pools": 45,
  "active_pools": 42,
  "inactive_pools": 3,
  "regions": [
    {
      "region": "us-east-1",
      "pools": 15,
      "average_price": 0.0105,
      "cheapest_pool": "us-east-1a-pool-2",
      "cheapest_price": 0.0089
    },
    {
      "region": "us-west-2",
      "pools": 12,
      "average_price": 0.0112,
      "cheapest_pool": "us-west-2b-pool-1",
      "cheapest_price": 0.0095
    }
  ],
  "instance_types": [
    {
      "instance_type": "t3.medium",
      "pools_available": 18,
      "avg_spot_price": 0.0104,
      "ondemand_price": 0.0416
    }
  ]
}
```

**Usage:** Admin overview, pool management
**Priority:** Medium (useful for capacity planning)

---

### 1.5 Agent Health Summary
**Frontend Method:** `getAgentHealth()`
**Current Behavior:** Returns `{ online: 0, offline: 0, total: 0 }`
**Recommended Backend Endpoint:** `GET /api/admin/agents/health-summary`

**Purpose:** Get aggregated agent health metrics
**Response:**
```json
{
  "total_agents": 24,
  "online": 20,
  "offline": 3,
  "deleted": 1,
  "by_client": [
    {
      "client_id": "client_uuid_1",
      "client_name": "Client A",
      "online": 5,
      "offline": 1,
      "total": 6
    }
  ],
  "recent_offline": [
    {
      "agent_id": "agent_uuid",
      "client_name": "Client B",
      "last_heartbeat": "2024-11-26T09:50:00Z",
      "offline_duration_minutes": 10
    }
  ],
  "heartbeat_distribution": {
    "healthy": 18,
    "degraded": 2,
    "critical": 1
  }
}
```

**Usage:** Admin dashboard, system health page
**Priority:** Medium (improves monitoring)

---

## 2. Recommended New Endpoints (From User Requirements)

These endpoints would enable features described in the user's frontend specification:

### 2.1 Real-Time Event Stream
**Recommended Endpoint:** `GET /api/events/stream` (Server-Sent Events)
**Alternative:** WebSocket at `ws://server/api/events/ws`

**Purpose:** Real-time updates for instance status, agent connectivity, switches
**Implementation:** Server-Sent Events (SSE) or WebSocket

**SSE Response (example):**
```
event: instance_status_change
data: {"instance_id": "i-123", "status": "running_primary", "timestamp": "2024-11-26T10:00:00Z"}

event: agent_status_change
data: {"agent_id": "agent_uuid", "status": "offline", "timestamp": "2024-11-26T10:01:00Z"}

event: switch_in_progress
data: {"agent_id": "agent_uuid", "switch_id": "switch_uuid", "status": "ami_creating"}
```

**Frontend Usage:**
```javascript
const eventSource = new EventSource('/api/events/stream');
eventSource.addEventListener('instance_status_change', (e) => {
  const data = JSON.parse(e.data);
  updateInstanceStatus(data.instance_id, data.status);
});
```

**Priority:** High (enables true real-time UI)
**Complexity:** Medium (requires SSE/WebSocket implementation)

---

### 2.2 Downtime Analytics
**Recommended Endpoint:** `GET /api/client/{client_id}/analytics/downtime`

**Purpose:** Detailed downtime analysis per client
**Response:**
```json
{
  "total_downtime_seconds": 456,
  "average_downtime_per_switch": 12,
  "switches_with_downtime": 38,
  "switches_without_downtime": 7,
  "downtime_by_trigger": {
    "automatic": {
      "total_seconds": 360,
      "average_seconds": 10,
      "count": 36
    },
    "manual": {
      "total_seconds": 48,
      "average_seconds": 24,
      "count": 2
    },
    "emergency": {
      "total_seconds": 48,
      "average_seconds": 8,
      "count": 6
    }
  },
  "longest_downtime": {
    "switch_id": "switch_uuid",
    "downtime_seconds": 45,
    "timestamp": "2024-11-20T14:00:00Z",
    "reason": "ami_creation_delay"
  }
}
```

**Usage:** Savings tab, analytics
**Priority:** Medium (valuable for SLA tracking)

---

### 2.3 Pool Volatility Indicators
**Recommended Endpoint:** `GET /api/client/instances/{instance_id}/pool-volatility`

**Purpose:** Get volatility/stability indicators for pools
**Response:**
```json
{
  "current_pool": {
    "pool_id": "us-east-1a-pool-1",
    "current_price": 0.0104,
    "volatility_score": 0.12,
    "volatility_category": "low",
    "interruption_rate_24h": 0.003,
    "price_stability_7d": "stable"
  },
  "alternative_pools": [
    {
      "pool_id": "us-east-1b-pool-2",
      "current_price": 0.0098,
      "volatility_score": 0.08,
      "volatility_category": "very_low",
      "interruption_rate_24h": 0.001,
      "price_stability_7d": "very_stable",
      "recommendation": "best"
    }
  ]
}
```

**Usage:** Manage Instances modal
**Priority:** High (mentioned in user requirements)

---

### 2.4 Emergency Mode Status
**Recommended Endpoint:** `GET /api/agents/{agent_id}/emergency-status`

**Purpose:** Check if agent is in emergency/fallback mode
**Response:**
```json
{
  "agent_id": "agent_uuid",
  "emergency_mode_active": false,
  "rebalance_only_mode": false,
  "ml_models_loaded": true,
  "decision_engine_active": true,
  "last_emergency_event": {
    "timestamp": "2024-11-20T08:00:00Z",
    "type": "rebalance_recommendation",
    "action_taken": "emergency_replica_created",
    "outcome": "success"
  },
  "emergency_replicas_count": 0,
  "termination_notices_24h": 0
}
```

**Usage:** Agent card, system health
**Priority:** Medium (helps understand agent state)

---

### 2.5 Bulk Operations
**Recommended Endpoint:** `POST /api/admin/bulk/execute`

**Purpose:** Execute operations on multiple entities
**Request:**
```json
{
  "operation": "delete_agents",
  "agent_ids": ["agent_uuid_1", "agent_uuid_2", "agent_uuid_3"],
  "confirm": true
}
```

**Response:**
```json
{
  "operation": "delete_agents",
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [
    {
      "agent_id": "agent_uuid_1",
      "status": "success"
    },
    {
      "agent_id": "agent_uuid_2",
      "status": "success"
    },
    {
      "agent_id": "agent_uuid_3",
      "status": "failed",
      "error": "Agent has active primary instance"
    }
  ]
}
```

**Usage:** Admin operations, batch management
**Priority:** Low (nice to have)

---

### 2.6 Pricing Alerts Configuration
**Recommended Endpoint:** `POST /api/client/{client_id}/pricing-alerts`

**Purpose:** Configure pricing alerts for notifications
**Request:**
```json
{
  "alert_type": "price_spike",
  "threshold": 0.015,
  "notification_channels": ["email", "dashboard"],
  "enabled": true
}
```

**Response:**
```json
{
  "alert_id": "alert_uuid",
  "alert_type": "price_spike",
  "threshold": 0.015,
  "enabled": true,
  "created_at": "2024-11-26T10:00:00Z"
}
```

**Usage:** Notifications system
**Priority:** Low (future enhancement)

---

### 2.7 Switch Simulation
**Recommended Endpoint:** `POST /api/client/instances/{instance_id}/simulate-switch`

**Purpose:** Simulate a switch to see expected savings and downtime
**Request:**
```json
{
  "target_pool": "us-east-1b-pool-3",
  "target_type": "spot"
}
```

**Response:**
```json
{
  "simulation": {
    "current_price": 0.0104,
    "target_price": 0.0089,
    "hourly_savings": 0.0015,
    "daily_savings": 0.036,
    "monthly_savings": 1.08,
    "estimated_downtime_seconds": 12,
    "confidence": 0.87,
    "volatility_risk": "low",
    "interruption_probability_24h": 0.002,
    "recommendation": "strongly_recommended"
  }
}
```

**Usage:** Manage Instances modal (before manual switch)
**Priority:** Medium (helps users make informed decisions)

---

## 3. Priority Matrix

| Priority | Endpoints | Total |
|----------|-----------|-------|
| **High** | Agent Statistics, Instance Logs, Pool Volatility, Real-Time Events | 4 |
| **Medium** | Global Search, Pool Statistics, Agent Health, Downtime Analytics, Emergency Status, Switch Simulation | 6 |
| **Low** | Bulk Operations, Pricing Alerts | 2 |

---

## 4. Implementation Recommendations

### Phase 1: Critical Functionality (High Priority)
1. **`GET /api/agents/{agent_id}/statistics`** - Agent Statistics
2. **`GET /api/client/instances/{instance_id}/logs`** - Instance Logs
3. **`GET /api/client/instances/{instance_id}/pool-volatility`** - Pool Volatility
4. **`GET /api/events/stream`** - Real-Time Event Stream (SSE)

**Impact:** Enables troubleshooting, provides critical insights, improves UX

---

### Phase 2: Enhanced Monitoring (Medium Priority)
5. **`GET /api/admin/search`** - Global Search
6. **`GET /api/admin/pools/statistics`** - Pool Statistics
7. **`GET /api/admin/agents/health-summary`** - Agent Health Summary
8. **`GET /api/client/{client_id}/analytics/downtime`** - Downtime Analytics
9. **`GET /api/agents/{agent_id}/emergency-status`** - Emergency Mode Status
10. **`POST /api/client/instances/{instance_id}/simulate-switch`** - Switch Simulation

**Impact:** Improves admin capabilities, better monitoring, informed decision-making

---

### Phase 3: Advanced Features (Low Priority)
11. **`POST /api/admin/bulk/execute`** - Bulk Operations
12. **`POST /api/client/{client_id}/pricing-alerts`** - Pricing Alerts

**Impact:** Convenience features, automation

---

## 5. Frontend Impact

### Endpoints That Will Unblock Frontend Features:

1. **SearchResultsPanel** (currently shows "not implemented")
   - Needs: `GET /api/admin/search`

2. **Instance Detail Panel** (limited debugging info)
   - Needs: `GET /api/client/instances/{instance_id}/logs`

3. **Manage Instances Modal** (missing volatility indicators)
   - Needs: `GET /api/client/instances/{instance_id}/pool-volatility`

4. **Live Updates** (currently uses polling every 5-10s)
   - Needs: `GET /api/events/stream` (SSE)
   - Benefit: Instant updates, reduced server load

5. **Agent Cards** (missing decision statistics)
   - Needs: `GET /api/agents/{agent_id}/statistics`

6. **System Health Page** (missing pool stats)
   - Needs: `GET /api/admin/pools/statistics`

---

## 6. Database Schema Additions

To support these endpoints, consider adding:

### New Tables:

1. **`instance_event_logs`**
   ```sql
   CREATE TABLE instance_event_logs (
     id VARCHAR(36) PRIMARY KEY,
     instance_id VARCHAR(36) NOT NULL,
     client_id VARCHAR(36) NOT NULL,
     agent_id VARCHAR(36),
     event_type VARCHAR(50) NOT NULL,
     severity VARCHAR(20) NOT NULL,
     message TEXT NOT NULL,
     metadata JSON,
     created_at DATETIME NOT NULL,
     INDEX idx_instance_id (instance_id),
     INDEX idx_created_at (created_at)
   );
   ```

2. **`agent_decision_statistics`** (materialized view or table)
   ```sql
   CREATE TABLE agent_decision_statistics (
     agent_id VARCHAR(36) PRIMARY KEY,
     total_decisions INT DEFAULT 0,
     switches_executed INT DEFAULT 0,
     switches_recommended INT DEFAULT 0,
     average_confidence DECIMAL(5,4),
     total_savings_generated DECIMAL(10,2),
     last_decision_at DATETIME,
     updated_at DATETIME NOT NULL
   );
   ```

3. **`pricing_alerts`**
   ```sql
   CREATE TABLE pricing_alerts (
     id VARCHAR(36) PRIMARY KEY,
     client_id VARCHAR(36) NOT NULL,
     alert_type VARCHAR(50) NOT NULL,
     threshold DECIMAL(10,6),
     enabled BOOLEAN DEFAULT TRUE,
     notification_channels JSON,
     created_at DATETIME NOT NULL
   );
   ```

---

## 7. Quick Implementation Checklist

For backend team to implement missing endpoints:

### High Priority (Do First):
- [ ] `GET /api/agents/{agent_id}/statistics` - Calculate from switches table
- [ ] `GET /api/client/instances/{instance_id}/logs` - Query instance_event_logs
- [ ] `GET /api/client/instances/{instance_id}/pool-volatility` - Analyze pricing_history
- [ ] `GET /api/events/stream` - Implement SSE endpoint

### Medium Priority (Do Second):
- [ ] `GET /api/admin/search` - Full-text search across tables
- [ ] `GET /api/admin/pools/statistics` - Aggregate spot_pools data
- [ ] `GET /api/admin/agents/health-summary` - Count agents by status
- [ ] `GET /api/client/{client_id}/analytics/downtime` - Analyze switches table
- [ ] `GET /api/agents/{agent_id}/emergency-status` - Check emergency flags
- [ ] `POST /api/client/instances/{instance_id}/simulate-switch` - Calculate simulation

### Low Priority (Future):
- [ ] `POST /api/admin/bulk/execute` - Batch operations handler
- [ ] `POST /api/client/{client_id}/pricing-alerts` - Alert management

---

## Summary

**Current Status:**
- ✅ 66 endpoints exist (68 including method variations)
- ❌ 5 endpoints return mock data (need implementation)
- 💡 7 endpoints recommended for enhanced functionality

**Total Missing/Recommended:** 12 endpoints

**Implementation Impact:**
- **High Priority (4):** Critical for core functionality
- **Medium Priority (6):** Significantly improves UX
- **Low Priority (2):** Nice-to-have features

**Next Steps:**
1. Implement High Priority endpoints first
2. Test with frontend integration
3. Add Medium Priority based on usage patterns
4. Consider Low Priority for future releases
