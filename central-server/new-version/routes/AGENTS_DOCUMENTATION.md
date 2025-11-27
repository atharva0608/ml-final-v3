# Agents Route Module Documentation

## Overview

The `agents.py` module handles all agent-related operations including registration, heartbeats, configuration, and statistics. This is the **most critical module** as agents are the primary interface between EC2 instances and the central server.

## Module Information

- **File**: `routes/agents.py`
- **Blueprint**: `agents_bp`
- **Total Endpoints**: 12
- **Lines of Code**: 1,163
- **Authentication**: All endpoints require client authentication via `@require_client_auth`

## Endpoints

### 1. Agent Registration
**POST `/api/agents/register`**

Registers a new agent or updates an existing agent's information.

**Key Features:**
- Creates new agent record or updates existing
- Validates instance isn't zombie/terminated
- Creates default configuration for new agents
- Sends notification on new agent registration
- Logs system event for audit trail

**Request Body:**
```json
{
  "logical_agent_id": "agent-hostname-123",
  "instance_id": "i-1234567890abcdef0",
  "instance_type": "t3.medium",
  "region": "us-east-1",
  "az": "us-east-1a",
  "mode": "spot",
  "hostname": "ip-10-0-1-100",
  "ami_id": "ami-123456",
  "agent_version": "4.0.0",
  "private_ip": "10.0.1.100",
  "public_ip": "54.123.45.67"
}
```

**Response:**
```json
{
  "agent_id": "uuid-generated",
  "client_id": "client-uuid",
  "config": {
    "enabled": true,
    "auto_switch_enabled": true,
    "auto_terminate_enabled": true,
    "terminate_wait_seconds": 300,
    "replica_enabled": false,
    "replica_count": 0,
    "min_savings_percent": 15.0,
    "risk_threshold": 0.30,
    "max_switches_per_week": 10,
    "min_pool_duration_hours": 2
  }
}
```

**Business Logic:**
1. Validates all required fields using `AgentRegistrationSchema`
2. Checks if agent with same `logical_agent_id` exists
3. If exists:
   - Checks if instance is zombie/terminated
   - Updates agent record if instance is valid
4. If new:
   - Generates UUID for agent_id
   - Inserts agent record
   - Creates default configuration
   - Sends notification to client
   - Logs system event

**Special Cases:**
- Zombie/terminated instances: Returns success but doesn't update agent
- Existing agents: Updates heartbeat and instance info
- New agents: Full initialization with default config

---

### 2. Agent Heartbeat
**POST `/api/agents/<agent_id>/heartbeat`**

Updates agent's last heartbeat timestamp and status.

**Purpose:**
- Keeps agent marked as "online"
- Updates current instance state
- Allows backend to detect offline agents
- Agents send heartbeat every 30-60 seconds

**Request Body:**
```json
{
  "timestamp": "2024-11-26T10:00:00Z",
  "status": "online",
  "current_mode": "spot",
  "current_pool_id": "t3.medium.us-east-1a",
  "spot_price": 0.0104,
  "ondemand_price": 0.0416
}
```

**Response:**
```json
{
  "success": true,
  "commands_pending": false,
  "config_version": 5
}
```

**Offline Detection:**
- Backend marks agent offline after 120 seconds of no heartbeat
- Implemented in background job (not in this module)

---

### 3. Get Agent Configuration
**GET `/api/agents/<agent_id>/config`**

Retrieves current configuration for an agent.

**Response:**
```json
{
  "agent_id": "uuid",
  "enabled": true,
  "auto_switch_enabled": true,
  "manual_replica_enabled": false,
  "auto_terminate_enabled": true,
  "terminate_wait_minutes": 5,
  "emergency_rebalance_only": false,
  "decision_engine_active": true,
  "config_version": 5,
  "min_savings_percent": 15.0,
  "risk_threshold": 0.30,
  "max_switches_per_week": 10,
  "min_pool_duration_hours": 2
}
```

**Configuration Versioning:**
- Each config change increments `config_version`
- Agents cache config locally
- Agents check version in heartbeat response
- Pull new config when version changes

---

### 4. Get Instances to Terminate
**GET `/api/agents/<agent_id>/instances-to-terminate`**

Returns list of instances ready for termination (zombies that exceeded wait time).

**Response:**
```json
[
  {
    "instance_id": "i-zombie-123",
    "reason": "zombie_instance",
    "age_hours": 168,
    "terminate_after": "2024-11-26T12:00:00Z"
  }
]
```

**Zombie Cleanup Logic:**
- Only includes instances where:
  - `instance_status = 'zombie'`
  - Current time > (switched_at + terminate_wait_seconds)
- Agent terminates these instances in AWS
- Reports back via cleanup-report endpoint

---

### 5. Termination Report
**POST `/api/agents/<agent_id>/termination-report`**

Records instance termination details.

**Request Body:**
```json
{
  "instance_id": "i-terminated-123",
  "reason": "manual|system|aws_termination",
  "timestamp": "2024-11-26T10:00:00Z",
  "termination_type": "graceful|forced"
}
```

---

### 6. Rebalance Recommendation
**POST `/api/agents/<agent_id>/rebalance-recommendation`**

Handles AWS EC2 rebalance recommendations (early warning before potential termination).

**Request Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "recommendation_time": "2024-11-26T10:00:00Z"
}
```

**Response:**
```json
{
  "success": true,
  "action_taken": "replica_created|replica_ready|no_action",
  "replica_id": "replica-uuid"
}
```

**Business Logic:**
- Checks if replica already exists
- If not, triggers emergency replica creation
- Logs event for monitoring
- Updates agent's last_rebalance_recommendation_at timestamp

---

### 7. Get Replica Configuration
**GET `/api/agents/<agent_id>/replica-config`**

Returns replica configuration settings for agent.

**Response:**
```json
{
  "manual_replica_enabled": true,
  "auto_create_replica": false,
  "preferred_replica_pools": ["us-east-1b-pool-2"],
  "replica_sync_required": true,
  "min_sync_percentage": 95
}
```

---

### 8. Get Decision (ML-based)
**POST `/api/agents/<agent_id>/decide`**

Submits instance state to decision engine for ML-based switching recommendation.

**Request Body:**
```json
{
  "current_state": {
    "instance_id": "i-current",
    "instance_type": "t3.medium",
    "current_mode": "spot",
    "current_pool": "us-east-1a-pool-1",
    "current_price": 0.0104
  },
  "pricing_data": {
    "available_pools": [
      {"pool_id": "us-east-1b-pool-1", "price": 0.0098}
    ],
    "ondemand_price": 0.0416
  },
  "metrics": {
    "uptime_hours": 24,
    "interruption_count": 0
  }
}
```

**Response:**
```json
{
  "recommendation": "switch|stay|switch_to_ondemand",
  "target_pool": "us-east-1b-pool-1",
  "confidence": 0.87,
  "reason": "Cost optimization: $0.015/hr savings",
  "expected_savings_per_day": 0.36,
  "risk_score": 0.12
}
```

---

### 9. Get Switch Recommendation
**GET `/api/agents/<agent_id>/switch-recommendation`**

Gets ML-based switch recommendation with will_auto_execute flag.

**Response:**
```json
{
  "recommendation": "switch",
  "target_pool": "us-east-1b-pool-3",
  "target_type": "spot",
  "confidence": 0.87,
  "reason": "Cost optimization: $0.015/hr savings with low volatility",
  "savings_impact": 0.015,
  "will_auto_execute": true
}
```

**Key Difference from /decide:**
- Returns `will_auto_execute` flag based on `auto_switch_enabled`
- Always returns recommendation even if auto_switch is OFF
- Used by frontend to show "what would happen"

---

### 10. Issue Switch Command
**POST `/api/agents/<agent_id>/issue-switch-command`**

Creates switch command in command queue (only if auto_switch_enabled = true).

**Request Body:**
```json
{
  "target_pool": "us-east-1b-pool-3",
  "confidence": 0.87,
  "reason": "cost_optimization"
}
```

**Response Success:**
```json
{
  "command_id": "uuid",
  "success": true
}
```

**Response Error (auto_switch disabled):**
```json
{
  "error": "Auto-switching is disabled for this agent",
  "code": "AUTO_SWITCH_DISABLED"
}
```
HTTP Status: 403 Forbidden

**Critical Behavior:**
- **CHECKS auto_switch_enabled before creating command**
- Returns 403 if auto_switch is OFF
- This is the enforcement point for the auto_switch setting

---

### 11. Get Agent Statistics
**GET `/api/agents/<agent_id>/statistics`**

Returns decision engine statistics and performance metrics.

**Response:**
```json
{
  "agent_id": "uuid",
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

**Data Sources:**
- switches table for executed switches
- agent_decision_history table for decisions
- Calculates success rate = switches / decisions

---

### 12. Get Emergency Status
**GET `/api/agents/<agent_id>/emergency-status`**

Checks if agent is in emergency or fallback mode.

**Response:**
```json
{
  "agent_id": "uuid",
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

---

## Key Database Tables Used

### agents
Primary agent information and status:
- id, client_id, logical_agent_id
- instance_id, instance_type, region, az
- current_mode, current_pool_id
- status, enabled, last_heartbeat_at
- auto_switch_enabled, auto_terminate_enabled
- manual_replica_enabled, replica_count

### agent_configs
Agent-specific configuration:
- min_savings_percent
- risk_threshold
- max_switches_per_week
- min_pool_duration_hours

### switches
Historical switch events for statistics

### agent_decision_history
ML decision history for analytics

### system_events
Audit trail of agent operations

---

## Important Business Rules

### 1. Zombie Instance Protection
- Registration from zombie/terminated instances is rejected
- Prevents zombie instances from becoming primary again
- Returns success but with disabled config

### 2. Auto-Switch Enforcement
- `/issue-switch-command` is the **only** enforcement point
- Checks `auto_switch_enabled` before creating command
- Returns 403 if disabled
- Frontend can still see recommendations

### 3. Configuration Versioning
- Every config change increments version
- Agents cache config locally
- Pull new config when version changes
- Reduces database queries

### 4. Heartbeat Timeout
- Agents send heartbeat every 30-60 seconds
- Backend marks offline after 120 seconds
- Background job handles timeout detection

---

## Error Handling

All endpoints follow standard error response format:

**Validation Errors (400):**
```json
{
  "error": "Validation failed",
  "details": {
    "instance_id": ["Missing required field"]
  }
}
```

**Authorization Errors (401/403):**
```json
{
  "error": "Invalid client token",
  "code": "INVALID_TOKEN"
}
```

**Not Found (404):**
```json
{
  "error": "Agent not found"
}
```

**Server Errors (500):**
```json
{
  "error": "Internal server error message"
}
```

---

## Logging

All endpoints log important events:
- Registration attempts
- Configuration changes
- Switch decisions
- Errors and warnings

**Log Locations:**
- `logs/backend_v5.log` - All logs
- `logs/error.log` - Errors only

---

## Testing

### Test Agent Registration
```bash
curl -X POST http://localhost:5000/api/agents/register \
  -H "Authorization: Bearer client-token" \
  -H "Content-Type: application/json" \
  -d '{
    "logical_agent_id": "test-agent-1",
    "instance_id": "i-test123",
    "instance_type": "t3.medium",
    "region": "us-east-1",
    "az": "us-east-1a",
    "mode": "spot"
  }'
```

### Test Heartbeat
```bash
curl -X POST http://localhost:5000/api/agents/agent-uuid/heartbeat \
  -H "Authorization: Bearer client-token" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2024-11-26T10:00:00Z",
    "status": "online"
  }'
```

### Test Configuration
```bash
curl http://localhost:5000/api/agents/agent-uuid/config \
  -H "Authorization: Bearer client-token"
```

---

## Performance Considerations

1. **Heartbeat Frequency**: High volume endpoint (every 30-60s per agent)
   - Keep queries simple
   - Use indexed columns
   - Consider caching config

2. **Decision Engine**: Can be slow for complex ML models
   - Implement timeouts
   - Consider async processing
   - Cache recent decisions

3. **Statistics Queries**: Can be expensive
   - Use indexes on switches.agent_id
   - Consider materialized views
   - Implement pagination for history

---

## Future Enhancements

1. **Agent Groups**: Manage multiple agents together
2. **Agent Roles**: Different permission levels
3. **Agent Metrics Dashboard**: Real-time performance monitoring
4. **Agent Auto-Discovery**: Automatic agent registration
5. **Agent Health Scoring**: Predictive health metrics

---

## Related Documentation

- Main README: `backend_v5/README.md`
- Auth Module: `core/auth.py`
- Validation Module: `core/validation.py`
- Database Layer: `core/database.py`
