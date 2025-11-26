# Central Server API Endpoints Report

## Frontend Overview

The central server frontend is a comprehensive control panel for managing AWS Spot instance optimization. It provides operators and clients with real-time visibility into instances, agents, replicas, savings, and system health. The frontend is built on React with a component-based architecture, using data visualization for pricing trends, savings analytics, and instance lifecycle tracking.

**Key Frontend Capabilities:**
- **Live State Visualization**: Displays real-time instance statuses, agent connectivity, and replica states through event streams/websocket mechanisms
- **Multi-Client Management**: Admin interface for managing multiple clients, their agents, and instances from a centralized dashboard
- **Decision Control**: Exposes toggles for auto-switching, manual replica management, and auto-termination, with all decisions validated by backend logic
- **Analytics & Reporting**: Shows savings calculations, downtime tracking, pricing history charts, and switch history with filtering capabilities
- **Agent Lifecycle Management**: Enables/disables agents, configures auto-switching settings, emergency fallback modes, and agent deletion with cleanup
- **Instance & Replica Control**: Manual switching between spot pools, on-demand conversion, replica creation/promotion/deletion, and pricing comparisons
- **Notification System**: Real-time alerts for instance changes, agent status updates, and system events

The frontend never makes autonomous decisions—all actions trigger backend validation and orchestration. When an agent goes offline, instances monitored by that agent are visually marked as offline. The UI reflects state transitions in real-time (e.g., "promoting" status during replica-to-primary promotion).

---

## How Savings Are Calculated

**Total Savings Calculation Method:**

The `total_savings` field displayed in the frontend is calculated and stored in the `clients` table. Here's how it works:

1. **Per-Switch Savings Calculation:**
   - When an instance switch occurs (e.g., from a more expensive pool to a cheaper pool), the backend calculates:
   ```
   savings_impact_per_hour = old_price - new_price
   ```
   - This hourly savings is then multiplied by 24 to estimate daily savings:
   ```
   daily_savings = savings_impact_per_hour * 24
   ```

2. **Cumulative Total:**
   - Every time a switch with positive savings occurs, the daily savings estimate is added to the client's `total_savings`:
   ```sql
   UPDATE clients
   SET total_savings = total_savings + (savings_impact * 24)
   WHERE id = client_id
   ```

3. **Data Source:**
   - Individual switch records are stored in the `switches` table with the `savings_impact` field
   - The `client_savings_monthly` table aggregates savings by month for charting
   - The `total_savings` in the `clients` table is the sum of all historical savings

**Important Notes:**
- The calculation uses a 24-hour multiplier as a simplified daily estimate when each switch occurs
- This assumes the savings continues for a full day (reasonable for most switches)
- The frontend displays this accumulated total in the dashboard and client detail views
- Actual runtime-based savings can be queried from the `switches` table for more precise analysis

---

## API Endpoints by Category

### 1. Admin Overview & Statistics (7 endpoints)

#### `GET /api/admin/stats`
Returns global statistics across all clients including:
- Total number of client accounts
- Agents online vs. total agents
- Total spot pools covered
- **Total savings** (sum of all clients' `total_savings` field)
- Total switches, manual switches, and ML-driven switches
- Backend health status
- Decision engine and ML model loading status

Used by the admin dashboard overview.

#### `GET /api/admin/clients`
Retrieves a list of all registered clients with:
- Client ID, name, email, status
- Agents online vs. total agents per client
- Instance count per client
- **Total savings per client** (from `clients.total_savings`)
- Creation date

Ordered by creation date (newest first). Powers the All Clients page.

#### `GET /api/admin/clients/growth?days={days}`
**Query Params:** `days` (default: 30)

Fetches client growth chart data showing daily client registration counts over the specified period. Returns time-series data for visualizing client acquisition trends in the admin dashboard.

#### `GET /api/admin/activity`
Returns recent activity log across all clients, including:
- Switch events (manual, automatic, emergency)
- Replica operations (creation, promotion, deletion)
- Agent status changes (online, offline, deleted)
- Configuration updates
- System-level events

Limited to recent events (typically last 100). Used for the admin activity log page.

#### `GET /api/admin/system-health`
Provides comprehensive system health metrics:
- Database connectivity status
- Connection pool utilization
- Agent health distribution (online, offline, total)
- Decision engine status (loaded, version, last update)
- ML model status (loaded, active session)
- Background job scheduler status
- System resource utilization (optional)

Used for monitoring and diagnostics.

#### `GET /api/admin/instances?status={status}&client_id={client_id}`
**Query Params:**
- `status`: 'all', 'active', 'terminated'
- `client_id`: Filter by specific client

Fetches all instances across all clients with optional filtering. Returns:
- Instance ID, type, region, availability zone
- Client name and ID
- Current mode (spot/on-demand), pool, pricing
- Status (running_primary, running_replica, zombie, terminated)
- Savings percentage vs. on-demand

Powers the global All Instances page.

#### `GET /api/admin/agents?status={status}&client_id={client_id}`
**Query Params:**
- `status`: 'all', 'online', 'offline'
- `client_id`: Filter by specific client

Retrieves all agents across all clients with:
- Agent ID, hostname, version
- Client name and ID
- Status (online/offline)
- Last heartbeat timestamp
- Associated instance ID
- Configuration summary

Used in the All Agents page.

---

### 2. Client Management (6 endpoints)

#### `POST /api/admin/clients/create`
**Body:** `{ "name": "Client Name", "email": "client@example.com" }`

Creates a new client account:
- Generates unique client ID (UUID)
- Generates secure authentication token (64-char random string)
- Initializes `total_savings` to 0
- Sets status to 'active'

Returns: `{ "client": { "id", "name", "email", "token" } }`

**Important:** The token is only returned once. Save it securely.

#### `DELETE /api/admin/clients/{client_id}`
Permanently deletes a client and all associated data:
- All agents belonging to the client
- All instances (active and terminated)
- All replicas
- All switch history
- All pricing data
- All notifications
- The client record itself

Requires confirmation in the frontend Delete Client modal. Irreversible operation.

#### `POST /api/admin/clients/{client_id}/regenerate-token`
Generates a new authentication token for the client:
- Invalidates the old token immediately
- Generates new 64-character secure token
- All existing agents using the old token will need to be updated

Used when token security is compromised or for regular security rotation.

Returns: `{ "token": "new_token_value" }`

#### `GET /api/admin/clients/{client_id}/token`
Retrieves the current authentication token for a client (admin only).

Used by the "View Token" modal to display the token for agent configuration.

Returns: `{ "token": "current_token_value" }`

**Security Note:** This endpoint should be admin-restricted and logged.

#### `GET /api/client/validate`
**Headers:** `Authorization: Bearer {client_token}`

Validates a client authentication token. Returns client information if valid, error if invalid/expired.

Used during client dashboard initialization to verify access credentials before loading data.

Returns: `{ "valid": true, "client_id": "...", "client_name": "..." }`

#### `GET /api/client/{client_id}`
Fetches detailed information about a specific client:
- Basic info (ID, name, email, status)
- **Total savings** (from `clients.total_savings`)
- Instance counts (active, terminated, zombie)
- Agent counts (online, offline, total)
- Last activity timestamp
- Configuration settings

Powers the client detail view header.

---

### 3. Agent Management (10 endpoints)

#### `POST /api/agents/register`
**Body:**
```json
{
  "token": "client_authentication_token",
  "hostname": "ip-10-0-1-100",
  "region": "us-east-1",
  "availability_zone": "us-east-1a",
  "instance_id": "i-1234567890abcdef0",
  "instance_type": "t3.medium",
  "agent_version": "4.0.0"
}
```

Registers a new agent with the central server:
- Validates client token
- Creates agent record with unique agent ID
- Associates agent with client
- Records initial heartbeat
- Sets status to 'online'

Called by agent startup scripts during bootstrap.

Returns: `{ "agent_id": "uuid", "config": {...} }`

#### `POST /api/agents/{agent_id}/heartbeat`
**Body:**
```json
{
  "timestamp": "2024-11-26T10:00:00Z",
  "status": "online",
  "instance_id": "i-1234567890abcdef0",
  "current_mode": "spot",
  "current_pool": "us-east-1a-spot-pool-1"
}
```

Sent periodically by agents (every 30-60 seconds) to:
- Update `last_heartbeat_at` timestamp
- Update agent status (online/offline determined by heartbeat timeout)
- Update current instance and pool information
- Trigger offline detection after timeout (default: 120 seconds)

Backend automatically marks agents offline if no heartbeat received within timeout.

Returns: `{ "success": true, "commands_pending": false }`

#### `GET /api/agents/{agent_id}/config`
Retrieves the current configuration for an agent:
```json
{
  "agent_id": "uuid",
  "auto_switch_enabled": true,
  "manual_replica_enabled": false,
  "auto_terminate_enabled": true,
  "terminate_wait_minutes": 30,
  "emergency_rebalance_only": false,
  "decision_engine_active": true
}
```

Used by agents to sync their configuration on startup and periodically during operation.

#### `POST /api/client/agents/{agent_id}/toggle-enabled`
**Body:** `{ "enabled": true }`

Enables or disables an agent:
- **When disabled:** Agent continues monitoring and sending heartbeats, but backend stops issuing switch commands
- **When enabled:** Agent resumes normal operation, receiving switch commands from the decision engine

Used by the agent card toggle switch in the Agents tab.

Returns: `{ "success": true, "enabled": true }`

#### `POST /api/client/agents/{agent_id}/settings`
**Body:** `{ "setting_name": "value", ... }`

Updates various agent settings. Legacy endpoint, mostly superseded by the `/config` endpoint.

Supports settings like polling intervals, logging levels, etc.

#### `POST /api/client/agents/{agent_id}/config`
**Body:**
```json
{
  "autoSwitchEnabled": true,
  "manualReplicaEnabled": false,
  "autoTerminateEnabled": true,
  "terminateWaitMinutes": 30
}
```

Updates agent configuration:
- **autoSwitchEnabled**: Enable/disable ML-driven automatic switching
- **manualReplicaEnabled**: Enable/disable manual replica mode (mutually exclusive with autoSwitchEnabled)
- **autoTerminateEnabled**: Auto-terminate old instances after switches (if false, instances become "zombies")
- **terminateWaitMinutes**: Minimum time to wait before terminating old instances

Used by the Agent Config Modal in the frontend.

**Important:** `autoSwitchEnabled` and `manualReplicaEnabled` are mutually exclusive. The frontend enforces this by disabling one when the other is enabled.

Returns: `{ "success": true }`

#### `DELETE /api/client/agents/{agent_id}`
Deletes an agent:
- Marks agent status as 'deleted'
- Marks all instances monitored by this agent as offline
- Triggers cleanup notification to the agent (if online)
- Removes pending commands
- Preserves historical data (switches, replicas) for audit trail

Used by the "Delete Agent" button in the agent card.

**Note:** Agent record is not physically deleted, only marked as deleted for historical tracking.

Returns: `{ "success": true }`

#### `GET /api/client/{client_id}/agents`
Retrieves all agents associated with a client:
```json
[
  {
    "id": "agent_uuid",
    "hostname": "ip-10-0-1-100",
    "status": "online",
    "last_heartbeat_at": "2024-11-26T10:00:00Z",
    "instance_id": "i-1234567890abcdef0",
    "current_mode": "spot",
    "current_pool": "us-east-1a-pool-1",
    "auto_switch_enabled": true,
    "manual_replica_enabled": false,
    "auto_terminate_enabled": true,
    "version": "4.0.0"
  }
]
```

Powers the Agents tab in the client detail view.

#### `GET /api/client/{client_id}/agents/decisions`
Fetches recent decision engine outputs for all agents of a client:
```json
[
  {
    "agent_id": "uuid",
    "timestamp": "2024-11-26T10:00:00Z",
    "recommendation": "switch",
    "target_pool": "us-east-1b-pool-3",
    "confidence": 0.87,
    "reason": "Cost optimization: $0.015/hr savings",
    "executed": true,
    "will_auto_execute": true
  }
]
```

Shows ML recommendations with confidence scores and execution status. Used in the Agent Decisions tab or Models tab.

#### `GET /api/client/{client_id}/agents/history`
Returns the full agent history including deleted agents:
```json
[
  {
    "id": "agent_uuid",
    "hostname": "ip-10-0-1-100",
    "status": "deleted",
    "created_at": "2024-10-01T10:00:00Z",
    "deleted_at": "2024-11-20T15:30:00Z",
    "total_switches": 45,
    "total_uptime_hours": 720
  }
]
```

Provides historical view of all agents that have ever been registered, including deleted ones. Useful for audit trails and historical analysis.

---

### 4. Instance Management (7 endpoints)

#### `GET /api/client/{client_id}/instances?status={status}&mode={mode}&search={search}`
**Query Params:**
- `status`: 'all', 'active', 'terminated'
- `mode`: 'all', 'spot', 'ondemand'
- `search`: Search by instance ID or name

Retrieves all instances for a client:
```json
[
  {
    "id": "i-1234567890abcdef0",
    "instance_type": "t3.medium",
    "region": "us-east-1",
    "az": "us-east-1a",
    "current_mode": "spot",
    "current_pool": "us-east-1a-pool-1",
    "spot_price": 0.0104,
    "ondemand_price": 0.0416,
    "instance_status": "running_primary",
    "is_primary": true,
    "is_active": true,
    "agent_id": "agent_uuid",
    "installed_at": "2024-11-01T10:00:00Z",
    "last_switch_at": "2024-11-20T14:00:00Z"
  }
]
```

Powers the Instances tab with filtering capabilities.

#### `GET /api/client/instances/{instance_id}/pricing`
Fetches current pricing information for an instance:
```json
{
  "instance_id": "i-1234567890abcdef0",
  "instance_type": "t3.medium",
  "current_spot_price": 0.0104,
  "ondemand_price": 0.0416,
  "current_pool": "us-east-1a-pool-1",
  "savings_vs_ondemand": 0.75,
  "savings_percentage": 75.0
}
```

Used for displaying pricing details in instance cards and modals.

#### `GET /api/client/instances/{instance_id}/metrics`
Returns runtime metrics for an instance:
```json
{
  "instance_id": "i-1234567890abcdef0",
  "uptime_hours": 168,
  "total_cost": 1.7472,
  "total_savings": 5.2416,
  "switch_count": 3,
  "last_switch": "2024-11-20T14:00:00Z",
  "interruption_count": 0,
  "avg_switch_downtime_seconds": 12
}
```

Shows accumulated metrics and performance statistics. Used in instance detail panels.

#### `GET /api/client/instances/{instance_id}/price-history?days={days}&interval={interval}`
**Query Params:**
- `days`: Number of days to retrieve (default: 7, max: 30)
- `interval`: 'hour', 'day' (default: 'hour')

Retrieves historical spot pricing data:
```json
[
  {
    "timestamp": "2024-11-26T10:00:00Z",
    "pool_id": "us-east-1a-pool-1",
    "spot_price": 0.0104,
    "ondemand_price": 0.0416
  }
]
```

Used to populate the pricing chart in the "Manage Instances" modal showing price trends across multiple pools.

#### `GET /api/client/pricing-history?client_id={client_id}&instance_type={type}&days={days}`
**Query Params:**
- `instance_type`: Filter by instance type (e.g., "t3.medium")
- `days`: Historical range (default: 7)

Returns historical pricing data across all pools for a specific instance type. Used for pricing trend analysis and forecasting.

#### `GET /api/client/instances/{instance_id}/available-options`
Returns available switching options for an instance:
```json
{
  "instance_id": "i-1234567890abcdef0",
  "current_pool": "us-east-1a-pool-1",
  "current_price": 0.0104,
  "ondemand_option": {
    "price": 0.0416,
    "savings_impact": -0.0312
  },
  "spot_pools": [
    {
      "pool_id": "us-east-1a-pool-2",
      "az": "us-east-1a",
      "current_price": 0.0098,
      "savings_impact": 0.0006,
      "volatility": "low",
      "recommendation": "best"
    },
    {
      "pool_id": "us-east-1b-pool-1",
      "az": "us-east-1b",
      "current_price": 0.0115,
      "savings_impact": -0.0011,
      "volatility": "medium"
    }
  ]
}
```

Sorted by current price (cheapest first). Used by the "Manage Instances" pricing modal to show available switch targets with pricing and stability indicators.

#### `POST /api/client/instances/{instance_id}/force-switch`
**Body:**
```json
{
  "target_pool": "us-east-1b-pool-3",
  "target_type": "spot",
  "auto_terminate": true
}
```

Manually forces a switch from the current instance to specified pool/type:
- Validates that only primary instances can be switched
- Creates a switch command for the agent
- Applies auto-termination and zombie rules based on configuration
- Broadcasts updated state to frontend

Used by the "Switch" buttons in the Manage Instances modal.

**Validation:**
- Only primary instances can be switched
- Target pool must be valid and available
- Switch to on-demand requires `target_type: "ondemand"`

Returns: `{ "success": true, "command_id": "uuid" }`

---

### 5. Replica Management (9 endpoints)

#### `GET /api/client/{client_id}/replicas`
Fetches all replicas associated with a client's instances:
```json
[
  {
    "replica_id": "uuid",
    "agent_id": "agent_uuid",
    "primary_instance_id": "i-primary-123",
    "replica_instance_id": "i-replica-456",
    "status": "ready",
    "sync_status": "synced",
    "sync_progress": 100,
    "pool_id": "us-east-1b-pool-2",
    "spot_price": 0.0102,
    "created_at": "2024-11-26T09:00:00Z",
    "ready_at": "2024-11-26T09:15:00Z",
    "replica_type": "manual"
  }
]
```

Powers the Replicas tab showing relationships between primaries and replicas.

#### `GET /api/agents/{agent_id}/replicas`
Returns replicas managed by a specific agent with detailed status:
```json
[
  {
    "id": "replica_uuid",
    "instance_id": "i-replica-456",
    "status": "ready",
    "sync_status": "synced",
    "sync_progress": 100,
    "created_at": "2024-11-26T09:00:00Z"
  }
]
```

Used by agents to check their replica status and by frontend for agent-specific replica views.

#### `GET /api/agents/{agent_id}/replica-config`
Retrieves replica configuration for an agent:
```json
{
  "manual_replica_enabled": true,
  "auto_create_replica": false,
  "preferred_replica_pools": ["us-east-1b-pool-2", "us-east-1c-pool-1"],
  "replica_sync_required": true,
  "min_sync_percentage": 95
}
```

Tells agents whether to maintain replicas and which pools to prefer.

#### `POST /api/agents/{agent_id}/replicas`
**Body:**
```json
{
  "target_pool": "us-east-1b-pool-2",
  "instance_type": "t3.medium",
  "sync_data": true
}
```

Creates a new replica for the agent's primary instance:
- Launches new instance in specified pool
- Initiates data synchronization
- Sets status to 'launching' → 'syncing' → 'ready'
- Records replica type (manual or automatic)

Used by:
- "Create Replica" button in the Replicas tab
- Manual replica mode (automatic creation)
- Emergency scenarios (automatic creation)

Returns: `{ "replica_id": "uuid", "instance_id": "i-replica-456" }`

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/promote`
**Body:**
```json
{
  "auto_terminate_old_primary": true,
  "create_new_replica": false
}
```

Promotes a replica to become the new primary:
- Updates replica status to 'promoted'
- Marks old primary as zombie or terminated (based on `auto_terminate_old_primary`)
- Updates agent's `instance_id` to point to new primary
- Optionally creates new replica if `create_new_replica` is true (in manual replica mode)

Used by:
- "Switch to Primary" button in the Replicas view
- Emergency termination handling (automatic promotion)

**Workflow:**
1. Replica is promoted to primary
2. Old primary becomes zombie (if auto_terminate=false) or terminated (if auto_terminate=true)
3. If manual replica mode is enabled and `create_new_replica=true`, a new replica is created for the newly promoted primary

Returns: `{ "success": true, "new_primary_id": "i-replica-456" }`

#### `DELETE /api/agents/{agent_id}/replicas/{replica_id}`
Deletes a replica instance:
- Terminates the replica instance on AWS
- Updates status to 'terminated'
- Records termination in history

**Important:** If manual replica mode is enabled, a new replica will be automatically created after deletion to maintain the "always one replica" policy.

Used by the "Delete Replica" button in the Replicas view.

Returns: `{ "success": true }`

#### `PUT /api/agents/{agent_id}/replicas/{replica_id}`
**Body:**
```json
{
  "sync_status": "syncing",
  "sync_progress": 75,
  "metadata": { "snapshot_id": "snap-123" }
}
```

Updates replica metadata or configuration. Used by agents to report replica state changes.

Returns: `{ "success": true }`

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/status`
**Body:**
```json
{
  "status": "ready",
  "message": "Replica sync completed successfully"
}
```

Updates the replica's operational status:
- 'launching': Instance is starting
- 'syncing': Data synchronization in progress
- 'ready': Replica is fully synced and ready for promotion
- 'error': Replica failed to sync or encountered error
- 'promoted': Replica has been promoted to primary
- 'terminated': Replica has been terminated

Called by agents during replica lifecycle transitions.

Returns: `{ "success": true }`

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/sync-status`
**Body:**
```json
{
  "sync_progress": 85,
  "sync_state": "syncing",
  "estimated_completion": "2024-11-26T11:00:00Z",
  "bytes_synced": 1073741824,
  "total_bytes": 1258291200
}
```

Updates the replication sync progress in real-time. Used to show:
- Progress percentage in the Replicas view
- Estimated completion time
- Sync throughput and statistics

Called periodically by agents during data synchronization.

Returns: `{ "success": true }`

---

### 6. Emergency & Advanced Operations (4 endpoints)

#### `POST /api/agents/{agent_id}/create-emergency-replica`
**Body:**
```json
{
  "reason": "rebalance_recommendation",
  "notice_time": "2024-11-26T10:00:00Z",
  "instance_id": "i-1234567890abcdef0"
}
```

Creates an emergency replica in response to AWS interruption signals:
- **Rebalance recommendation**: Early warning (typically 2+ hours notice)
- **Termination notice**: 2-minute warning

**CRITICAL BEHAVIOR:**
- **Bypasses all settings** including `manual_replica_enabled` and `auto_switch_enabled`
- Always executes as a safety mechanism
- Works even if ML models are not loaded or broken
- Creates replica immediately in the safest/cheapest available pool

Workflow:
1. AWS sends rebalance/termination notice to agent
2. Agent calls this endpoint
3. Backend creates replica OR promotes existing replica
4. No checks for auto_switch, auto_replica, or ML model state

Returns: `{ "replica_id": "uuid", "instance_id": "i-replica-789" }`

#### `POST /api/agents/{agent_id}/termination-imminent`
**Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "termination_time": "2024-11-26T10:02:00Z",
  "replica_id": "replica_uuid"
}
```

Handles the **2-minute termination warning** from AWS:
- Immediately promotes existing replica to primary (if available)
- Completes failover in <15 seconds typically
- **Bypasses all settings and ML models**
- Works even if decision engine is offline

**CRITICAL BEHAVIOR:**
- This is the fastest failover path
- If no replica exists, triggers emergency snapshot (slower, ~3-5 minutes)
- Ensures minimal downtime during spot interruptions

Workflow:
1. AWS sends termination notice with 2-minute warning
2. Agent identifies ready replica
3. Agent calls this endpoint
4. Backend immediately promotes replica
5. Old instance is terminated by AWS at scheduled time

Returns: `{ "success": true, "new_primary_id": "i-replica-456", "failover_time_ms": 8500 }`

#### `POST /api/agents/{agent_id}/rebalance-recommendation`
**Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "recommendation_time": "2024-11-26T10:00:00Z"
}
```

Reports AWS rebalance recommendation (early warning):
- Typically gives 2+ hours notice before potential termination
- Triggers creation of emergency replica if one doesn't exist
- Less urgent than termination notice
- Allows graceful preparation for possible interruption

Workflow:
1. AWS sends rebalance recommendation via instance metadata
2. Agent calls this endpoint
3. If no replica exists, backend creates one
4. If replica exists, backend ensures it's ready
5. System is prepared for potential termination

Returns: `{ "success": true, "replica_status": "creating|ready" }`

#### `POST /api/agents/{agent_id}/termination`
**Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "reason": "manual|system|aws_notice",
  "timestamp": "2024-11-26T10:00:00Z",
  "termination_type": "graceful|forced"
}
```

Reports instance termination completion:
- Updates instance status to 'terminated'
- Records termination details in history
- Updates agent status if primary instance was terminated
- Calculates final cost and runtime metrics

Used after instance has actually terminated (post-mortem reporting).

Returns: `{ "success": true }`

---

### 7. Decision Engine & ML Integration (8 endpoints)

#### `GET /api/agents/{agent_id}/switch-recommendation`
Returns the ML-based recommendation for switching pools:
```json
{
  "recommendation": "switch",
  "target_pool": "us-east-1b-pool-3",
  "target_type": "spot",
  "confidence": 0.87,
  "reason": "Cost optimization: $0.015/hr savings with low volatility",
  "savings_impact": 0.015,
  "will_auto_execute": true,
  "features_used": {
    "current_price": 0.0104,
    "target_price": 0.0089,
    "volatility_score": 0.12,
    "interruption_rate": 0.003
  }
}
```

**Important:**
- Always returns ML recommendation, even if `auto_switch_enabled` is OFF
- The `will_auto_execute` flag indicates whether the backend will automatically issue switch command
- If `auto_switch_enabled` is OFF, shows as suggestion only (no action taken)
- If `auto_switch_enabled` is ON, recommendation will be automatically executed

Used by agents to understand what the ML model suggests and by frontend to show "what would happen" scenarios.

#### `POST /api/agents/{agent_id}/issue-switch-command`
**Body:**
```json
{
  "target_pool": "us-east-1b-pool-3",
  "confidence": 0.87,
  "reason": "cost_optimization"
}
```

Issues a switch command based on ML recommendation:

**CRITICAL BEHAVIOR:**
- **Checks `auto_switch_enabled` before creating command**
- If `auto_switch_enabled` is OFF: Returns `403 Forbidden` error
- If `auto_switch_enabled` is ON: Creates switch command in 'commands' table

Workflow (when auto_switch is ON):
1. ML model recommends switch
2. This endpoint creates command
3. Agent polls `/pending-commands`
4. Agent executes switch
5. Agent reports completion via `/switch-report`

Returns:
- Success: `{ "command_id": "uuid", "success": true }`
- Forbidden: `{ "error": "Auto-switching is disabled for this agent", "code": "AUTO_SWITCH_DISABLED" }` (403)

#### `POST /api/agents/{agent_id}/decide`
**Body:**
```json
{
  "current_state": {
    "instance_id": "i-1234567890abcdef0",
    "instance_type": "t3.medium",
    "current_mode": "spot",
    "current_pool": "us-east-1a-pool-1",
    "current_price": 0.0104
  },
  "pricing_data": {
    "available_pools": [
      {"pool_id": "us-east-1a-pool-2", "price": 0.0098},
      {"pool_id": "us-east-1b-pool-1", "price": 0.0115}
    ],
    "ondemand_price": 0.0416
  },
  "metrics": {
    "uptime_hours": 24,
    "interruption_count": 0
  }
}
```

Submits current instance state to the decision engine for analysis:
- Runs ML model inference
- Considers pricing trends, volatility, interruption rates
- Calculates expected savings vs. risk
- Returns recommendation with confidence score

Called periodically by agents (e.g., every 15-30 minutes) for decision evaluation.

Returns:
```json
{
  "recommendation": "stay|switch|switch_to_ondemand",
  "target_pool": "us-east-1b-pool-3",
  "confidence": 0.87,
  "reason": "Detailed explanation...",
  "expected_savings_per_day": 0.36
}
```

#### `POST /api/admin/decision-engine/upload`
**Body:** Multipart form data

Uploads decision engine Python files:
- Supported extensions: `.py`, `.pkl`, `.joblib`
- Files are saved to `DECISION_ENGINE_DIR` (default: `./decision_engines/`)
- Triggers automatic backend reload to activate new code

**Usage:**
1. Upload new decision engine implementation
2. Backend restarts automatically (in dev mode) or requires manual restart (in production)
3. New decision engine class is loaded on restart

Files typically include:
- `ml_based_engine.py`: Decision engine implementation
- Model files: `.pkl`, `.joblib` (if needed by engine)

Returns: `{ "success": true, "files_uploaded": ["file1.py", "file2.pkl"] }`

#### `POST /api/admin/ml-models/upload`
**Body:** Multipart form data

Uploads ML model files to the server:
- Supported extensions: `.pkl`, `.joblib`, `.h5`, `.pb`, `.pth`, `.onnx`, `.pt`
- Creates new model session with timestamp (e.g., `20241126_100000`)
- Files saved to `MODEL_DIR/{session_id}/`
- Does NOT activate automatically (use `/activate` endpoint)

**Workflow:**
1. Upload model files
2. Files stored in timestamped session directory
3. Session appears in `/ml-models/sessions` list
4. Use `/activate` to switch to new models

Returns:
```json
{
  "success": true,
  "session_id": "20241126_100000",
  "files_uploaded": ["model.pkl", "scaler.joblib"]
}
```

#### `POST /api/admin/ml-models/activate`
**Body:**
```json
{
  "sessionId": "20241126_100000"
}
```

Activates a previously uploaded ML model session:
- Triggers backend restart to load new models
- **RED RESTART button** in the admin UI
- Previous model session is deactivated
- Decision engine reloads with new model files

**IMPORTANT:**
- Causes brief service interruption during restart
- Agents will reconnect automatically
- In-flight decisions may be lost

Returns: `{ "success": true, "restarting": true }`

#### `POST /api/admin/ml-models/fallback`
Falls back to the previous ML model session:
- Reverts to last known good model state
- Used when current models are broken or performing poorly
- Triggers backend reload

**Use Case:**
1. New models activated but performing poorly
2. Admin clicks "Fallback to Previous" button
3. System reverts to previous session
4. Service restarts with old models

Returns: `{ "success": true, "fallback_session": "20241120_143000" }`

#### `GET /api/admin/ml-models/sessions`
Retrieves list of all ML model upload sessions:
```json
[
  {
    "session_id": "20241126_100000",
    "upload_time": "2024-11-26T10:00:00Z",
    "files": ["model.pkl", "scaler.joblib", "feature_selector.pkl"],
    "active": true,
    "file_sizes": [524288, 102400, 51200]
  },
  {
    "session_id": "20241120_143000",
    "upload_time": "2024-11-20T14:30:00Z",
    "files": ["old_model.pkl"],
    "active": false,
    "file_sizes": [487424]
  }
]
```

Shows all available model sessions with metadata. Used in the Client Models tab to:
- View upload history
- Select session to activate
- Identify current active session

Returns array ordered by upload time (newest first).

---

### 8. Command & Execution Tracking (2 endpoints)

#### `GET /api/agents/{agent_id}/pending-commands`
Fetches pending commands for an agent to execute:
```json
[
  {
    "command_id": "uuid",
    "command_type": "switch",
    "target_pool": "us-east-1b-pool-3",
    "target_mode": "spot",
    "priority": "normal",
    "created_at": "2024-11-26T10:00:00Z",
    "expires_at": "2024-11-26T11:00:00Z",
    "parameters": {
      "auto_terminate": true,
      "sync_data": true
    }
  }
]
```

**Agent Polling:**
- Agents poll this endpoint regularly (every 30-60 seconds)
- Commands can be: 'switch', 'create_replica', 'promote_replica', 'terminate', 'update_config'
- Commands have expiration time (typically 1 hour)
- Expired commands are automatically removed

Workflow:
1. Backend creates command (via `/issue-switch-command` or decision engine)
2. Command inserted into `commands` table with status 'pending'
3. Agent polls this endpoint
4. Agent receives command
5. Agent executes command
6. Agent reports completion via `/commands/{id}/executed`

Returns array of pending commands, ordered by priority and creation time.

#### `POST /api/agents/{agent_id}/commands/{command_id}/executed`
**Body:**
```json
{
  "status": "success",
  "execution_time": "2024-11-26T10:05:00Z",
  "duration_seconds": 45,
  "error": null,
  "result": {
    "new_instance_id": "i-new-instance",
    "downtime_seconds": 8
  }
}
```

Confirms command execution by the agent:
- Updates command status to 'success' or 'failed'
- Records execution timestamp and duration
- Stores error message if failed
- Used for audit trail and monitoring

**Status values:**
- `success`: Command executed successfully
- `failed`: Command execution failed (includes error message)
- `partial`: Command partially executed (rare)

Returns: `{ "success": true }`

---

### 9. Reporting & Telemetry (4 endpoints)

#### `POST /api/agents/{agent_id}/pricing-report`
**Body:**
```json
{
  "instance_id": "i-1234567890abcdef0",
  "instance_type": "t3.medium",
  "region": "us-east-1",
  "spot_prices": [
    {
      "pool_id": "us-east-1a-pool-1",
      "az": "us-east-1a",
      "price": 0.0104,
      "timestamp": "2024-11-26T10:00:00Z"
    },
    {
      "pool_id": "us-east-1b-pool-1",
      "az": "us-east-1b",
      "price": 0.0098,
      "timestamp": "2024-11-26T10:00:00Z"
    }
  ],
  "on_demand_price": 0.0416
}
```

Submits current spot pricing data from AWS:
- Called periodically by agents (every 5-15 minutes)
- Populates pricing history for charts
- Used by decision engine for trend analysis
- Stored in `spot_pricing_history` table

**Data Usage:**
- Powers pricing charts in "Manage Instances" modal
- Feeds into ML model for price prediction
- Used for volatility calculations

Returns: `{ "success": true, "records_inserted": 2 }`

#### `POST /api/agents/{agent_id}/switch-report`
**Body:**
```json
{
  "command_id": "uuid",
  "old_instance": {
    "instance_id": "i-old-123",
    "instance_type": "t3.medium",
    "mode": "spot",
    "pool_id": "us-east-1a-pool-1",
    "az": "us-east-1a",
    "ami_id": "ami-123",
    "region": "us-east-1"
  },
  "new_instance": {
    "instance_id": "i-new-456",
    "instance_type": "t3.medium",
    "mode": "spot",
    "pool_id": "us-east-1b-pool-2",
    "az": "us-east-1b",
    "ami_id": "ami-456",
    "region": "us-east-1"
  },
  "pricing": {
    "old_spot": 0.0104,
    "new_spot": 0.0098,
    "on_demand": 0.0416
  },
  "timing": {
    "initiated_at": "2024-11-26T10:00:00Z",
    "ami_created_at": "2024-11-26T10:02:00Z",
    "instance_launched_at": "2024-11-26T10:04:00Z",
    "instance_ready_at": "2024-11-26T10:04:12Z",
    "old_terminated_at": "2024-11-26T10:05:00Z"
  },
  "trigger": "automatic",
  "downtime_seconds": 12
}
```

Reports completion of a switch operation:
- Calculates `savings_impact = old_price - new_price`
- **Updates `clients.total_savings += savings_impact * 24`** (daily savings estimate)
- Stores switch record in `switches` table
- Marks old instance as terminated or zombie based on `auto_terminate_enabled`
- Registers new instance as primary
- Creates notification

**Savings Calculation Detail:**
```python
savings_impact_per_hour = old_spot_price - new_spot_price
daily_savings = savings_impact_per_hour * 24
total_savings += daily_savings  # Accumulated in clients.total_savings
```

This is a simplified estimate assuming the savings continues for 24 hours.

Returns: `{ "success": true }`

#### `POST /api/agents/{agent_id}/cleanup-report`
**Body:**
```json
{
  "instances_cleaned": ["i-zombie-123", "i-zombie-456"],
  "resources_freed": {
    "ebs_volumes": 2,
    "snapshots": 0,
    "elastic_ips": 0
  },
  "cost_impact": 0.008
}
```

Reports cleanup operations performed by the agent:
- Terminating zombie instances
- Removing old replicas
- Cleaning up orphaned resources
- Deleting old snapshots

Used for tracking resource cleanup and cost optimization.

Returns: `{ "success": true }`

#### `GET /api/agents/{agent_id}/instances-to-terminate`
Returns list of instances that should be terminated:
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

Based on:
- `auto_terminate_enabled` setting
- `terminate_wait_minutes` configuration
- Zombie cleanup policies

Agents poll this periodically and terminate instances that have aged beyond the wait period.

Returns array of instances ready for termination.

---

### 10. Savings & Analytics (4 endpoints)

#### `GET /api/client/{client_id}/savings?range={range}`
**Query Params:** `range` = 'daily' | 'weekly' | 'monthly' | 'yearly' (default: 'monthly')

Calculates savings compared to on-demand baseline:
```json
[
  {
    "name": "November",
    "savings": 124.80,
    "onDemandCost": 249.60,
    "modelCost": 124.80
  },
  {
    "name": "December",
    "savings": 156.24,
    "onDemandCost": 312.48,
    "modelCost": 156.24
  }
]
```

**Data Source:**
- Monthly aggregates from `client_savings_monthly` table
- `savings` = baseline_cost - actual_cost
- Baseline cost = what would have been paid for all on-demand
- Actual cost = what was actually paid (spot + on-demand)

Powers the Savings view with chart visualization.

**Important:** This is different from `clients.total_savings`, which is a cumulative running total. This endpoint provides time-series data for charting.

#### `GET /api/client/{client_id}/switch-history?instance_id={instance_id}`
**Query Params:** `instance_id` (optional) - Filter by specific instance

Retrieves switch history for a client:
```json
[
  {
    "id": "switch_uuid",
    "oldInstanceId": "i-old-123",
    "newInstanceId": "i-new-456",
    "timestamp": "2024-11-26T10:04:00Z",
    "fromMode": "spot",
    "toMode": "spot",
    "fromPool": "us-east-1a-pool-1",
    "toPool": "us-east-1b-pool-2",
    "trigger": "automatic",
    "price": 0.0098,
    "savingsImpact": 0.0006
  }
]
```

Shows all switch events with:
- From/to instance IDs
- From/to pools and modes
- Trigger type (manual, automatic, emergency)
- Pricing and savings impact
- Timestamps

Limited to last 100 switches. Used in the History view with filtering.

#### `GET /api/client/{client_id}/stats/charts`
Fetches chart data for the client detail view:
```json
{
  "instance_count_over_time": [
    {"date": "2024-11-01", "count": 5},
    {"date": "2024-11-08", "count": 7}
  ],
  "savings_trend": [
    {"date": "2024-11-01", "savings": 12.50},
    {"date": "2024-11-08", "savings": 15.80}
  ],
  "switch_frequency": [
    {"date": "2024-11-01", "switches": 3},
    {"date": "2024-11-08", "switches": 2}
  ],
  "downtime_distribution": {
    "automatic": 45,
    "manual": 12,
    "emergency": 8
  }
}
```

Aggregated statistics for visualization in the Overview tab charts.

#### `GET /api/client/pricing-history?client_id={client_id}&instance_type={type}&days={days}`
**Query Params:**
- `client_id`: Target client
- `instance_type`: Filter by type (e.g., "t3.medium")
- `days`: Historical range (default: 7, max: 90)

Returns historical pricing data across pools:
```json
[
  {
    "timestamp": "2024-11-26T10:00:00Z",
    "pool_id": "us-east-1a-pool-1",
    "az": "us-east-1a",
    "spot_price": 0.0104,
    "ondemand_price": 0.0416
  }
]
```

Used for pricing trend analysis, forecasting, and decision-making.

---

### 11. Export & Download (3 endpoints)

#### `GET /api/client/{client_id}/export/savings`
Generates and downloads a CSV export of savings data:

**CSV Format:**
```
Year,Month,Month Name,On-Demand Cost ($),Actual Cost ($),Savings ($)
2024,11,November,249.60,124.80,124.80
2024,12,December,312.48,156.24,156.24
```

**Behavior:**
- Returns CSV file directly (Content-Type: text/csv)
- Opens in new browser tab via `window.open()`
- Includes historical monthly savings data

#### `GET /api/client/{client_id}/export/switch-history`
Generates and downloads a CSV export of switch history:

**CSV Format:**
```
Timestamp,Old Instance,New Instance,From Pool,To Pool,Trigger,Downtime (s),Savings Impact ($/hr)
2024-11-26 10:04:00,i-old-123,i-new-456,us-east-1a-pool-1,us-east-1b-pool-2,automatic,12,0.0006
```

**Behavior:**
- Returns CSV file directly
- Opens in new browser tab
- Includes last 1000 switch events

#### `GET /api/admin/export/global-stats`
Generates comprehensive CSV export of global statistics (admin only):

**CSV Format:**
```
Client ID,Client Name,Instances,Agents Online,Total Agents,Total Savings ($),Created At
uuid-1,Client A,5,3,4,1248.50,2024-10-01
uuid-2,Client B,2,1,2,567.20,2024-11-15
```

**Behavior:**
- Admin-only endpoint
- Exports all clients with key metrics
- Sorted by total savings (highest first)

---

### 12. Notifications (3 endpoints)

#### `GET /api/notifications?client_id={client_id}&limit={limit}`
**Query Params:**
- `client_id`: Filter by client (optional for admin)
- `limit`: Max notifications to return (default: 10, max: 100)

Fetches notifications:
```json
{
  "unread_count": 5,
  "notifications": [
    {
      "id": "notif_uuid",
      "type": "info",
      "message": "Instance switched: i-new-456 - Saved $0.0006/hr",
      "client_id": "client_uuid",
      "timestamp": "2024-11-26T10:04:00Z",
      "read": false,
      "metadata": {
        "instance_id": "i-new-456",
        "savings": 0.0006
      }
    }
  ]
}
```

**Notification Types:**
- `info`: General information
- `warning`: Warning messages (e.g., high spot price volatility)
- `error`: Error conditions (e.g., switch failed)
- `success`: Success confirmations

Used by the notification panel in the header.

#### `POST /api/notifications/{notif_id}/mark-read`
Marks a specific notification as read:
- Updates `read` flag to true
- Decrements unread count
- Timestamp when marked read

Called when user clicks on a notification.

Returns: `{ "success": true }`

#### `POST /api/notifications/mark-all-read`
**Body:** `{ "client_id": "optional_client_id" }`

Marks all notifications as read:
- For specific client if `client_id` provided
- For all clients if called by admin without `client_id`

Used by the "Mark All as Read" button in the notification panel.

Returns: `{ "success": true, "marked_count": 12 }`

---

### 13. Health & Monitoring (1 endpoint)

#### `GET /health`
Simple health check endpoint:
```json
{
  "status": "healthy",
  "timestamp": "2024-11-26T10:00:00Z",
  "version": "4.3.0",
  "uptime_seconds": 86400
}
```

**Usage:**
- Load balancer health checks
- Monitoring systems (Nagios, Prometheus, etc.)
- Startup verification
- Returns 200 OK if server is running
- Returns 503 Service Unavailable if unhealthy

**Health Criteria:**
- Database connectivity
- Decision engine loaded (optional, warning only)
- Background scheduler running

---

## API Design Principles

1. **RESTful Architecture**: All endpoints follow REST conventions with appropriate HTTP methods (GET for retrieval, POST for creation/actions, PUT for updates, DELETE for removal).

2. **Consistent Response Format**: All endpoints return JSON with consistent structure:
   ```json
   {
     "status": "success",
     "data": { ... },
     "error": null
   }
   ```
   Or on error:
   ```json
   {
     "status": "error",
     "error": "Error message",
     "data": null
   }
   ```

3. **Authentication**: Client-specific endpoints require authentication token in headers. Admin endpoints require admin credentials.

4. **Filtering & Pagination**: List endpoints support query parameters for filtering, sorting, and pagination to handle large datasets efficiently.

5. **Idempotency**: Critical operations (like replica creation, switch commands) are idempotent to prevent duplicate actions from retries.

6. **Bypass Mechanisms**: Emergency endpoints (`create-emergency-replica`, `termination-imminent`) bypass normal settings and ML models to ensure safety and availability.

7. **Real-time Updates**: The backend supports periodic polling (agents poll every 30-60 seconds for commands, frontend refreshes every 5-10 seconds for live data) to approximate real-time updates.

8. **Validation**: All endpoints perform input validation and return appropriate 400 Bad Request errors with descriptive messages for invalid inputs.

---

## Summary

The central server API provides **59 distinct endpoints** organized into 13 functional categories. These endpoints enable comprehensive management of:

- Multi-client infrastructure with isolation
- Agent registration, lifecycle, and configuration
- Instance and replica orchestration
- Emergency failover and safety mechanisms
- ML-driven decision making with manual override capability
- Real-time monitoring and notifications
- Analytics, savings calculations, and historical reporting
- Administrative controls and system health monitoring

### Key Architectural Features:

**Savings Calculation:**
- Cumulative `total_savings` field in `clients` table
- Updated on each switch: `savings_impact * 24` (daily estimate)
- Historical data in `switches` and `client_savings_monthly` tables
- Frontend displays accumulated total from `clients.total_savings`

**Safety Mechanisms:**
- Emergency endpoints bypass all settings (`auto_switch_enabled`, `manual_replica_enabled`)
- 2-minute termination handling with <15 second failover
- Automatic replica creation on AWS interruption signals
- Works even when ML models are offline or broken

**Flexibility:**
- Manual override capability for all automated decisions
- Toggle between auto-switching and manual replica modes
- Configurable auto-termination (zombie instances when disabled)
- Per-agent configuration granularity

**Visibility:**
- Comprehensive telemetry and reporting
- Real-time status updates via polling
- Historical tracking for audit trails
- Export capabilities for external analysis

The API design prioritizes **safety** (emergency bypass mechanisms), **flexibility** (manual overrides for automation), **visibility** (comprehensive telemetry and reporting), and **scalability** (connection pooling, background jobs, efficient queries).
# Central Server API Endpoints - Complete Reference Table

**Total Endpoints: 66 unique paths (68 total including method variations)**

## Endpoint Count Explanation
- **Initial Report**: Said 65 endpoints (incorrect count)
- **Corrected Report**: Said 59 endpoints (only counted non-indented routes)
- **Actual Total**: **66 unique endpoint paths**
  - 59 standard routes (direct `@app.route` decorators)
  - 7 additional routes from replica management (dynamically registered)
  - Some paths support multiple HTTP methods (GET/POST/PUT/DELETE)

---

## Complete Endpoint Reference

| # | Endpoint | Method | Description | Usage |
|---|----------|--------|-------------|-------|
| **ADMIN - OVERVIEW & STATISTICS** |
| 1 | `/api/admin/stats` | GET | Get global statistics (clients, agents, savings, switches) | ✅ Frontend |
| 2 | `/api/admin/clients` | GET | List all clients with metadata and stats | ✅ Frontend |
| 3 | `/api/admin/clients/growth` | GET | Client growth chart data over time | ✅ Frontend |
| 4 | `/api/admin/activity` | GET | Recent activity log across all clients | ✅ Frontend |
| 5 | `/api/admin/system-health` | GET | System health metrics and diagnostics | ✅ Frontend |
| 6 | `/api/admin/instances` | GET | All instances across all clients (admin view) | ✅ Frontend |
| 7 | `/api/admin/agents` | GET | All agents across all clients (admin view) | ✅ Frontend |
| **ADMIN - CLIENT MANAGEMENT** |
| 8 | `/api/admin/clients/create` | POST | Create new client account with token | ✅ Frontend |
| 9 | `/api/admin/clients/<client_id>` | DELETE | Delete client and all associated data | ✅ Frontend |
| 10 | `/api/admin/clients/<client_id>/regenerate-token` | POST | Regenerate client authentication token | ✅ Frontend |
| 11 | `/api/admin/clients/<client_id>/token` | GET | Retrieve client authentication token | ✅ Frontend |
| **ADMIN - ML & DECISION ENGINE** |
| 12 | `/api/admin/decision-engine/upload` | POST | Upload decision engine Python files | ✅ Frontend |
| 13 | `/api/admin/ml-models/upload` | POST | Upload ML model files (pkl, h5, pth, etc.) | ✅ Frontend |
| 14 | `/api/admin/ml-models/activate` | POST | Activate uploaded ML model session | ✅ Frontend |
| 15 | `/api/admin/ml-models/fallback` | POST | Fallback to previous ML model session | ✅ Frontend |
| 16 | `/api/admin/ml-models/sessions` | GET | List all ML model upload sessions | ✅ Frontend |
| **ADMIN - EXPORTS** |
| 17 | `/api/admin/export/global-stats` | GET | Export global statistics as CSV | ✅ Frontend |
| **CLIENT - AUTHENTICATION & INFO** |
| 18 | `/api/client/validate` | GET | Validate client authentication token | ⚠️ Not Used |
| 19 | `/api/client/<client_id>` | GET | Get client details and summary | ✅ Frontend |
| **CLIENT - AGENTS** |
| 20 | `/api/client/<client_id>/agents` | GET | List all agents for a client | ✅ Frontend |
| 21 | `/api/client/<client_id>/agents/decisions` | GET | Get recent ML decision outputs | ✅ Frontend |
| 22 | `/api/client/<client_id>/agents/history` | GET | Get agent history including deleted | ✅ Frontend |
| 23 | `/api/client/agents/<agent_id>/toggle-enabled` | POST | Enable/disable agent | ✅ Frontend |
| 24 | `/api/client/agents/<agent_id>/settings` | POST | Update agent settings (legacy) | ⚠️ Not Used |
| 25 | `/api/client/agents/<agent_id>/config` | POST | Update agent configuration | ✅ Frontend |
| 26 | `/api/client/agents/<agent_id>` | DELETE | Delete agent | ✅ Frontend |
| **CLIENT - INSTANCES** |
| 27 | `/api/client/<client_id>/instances` | GET | List instances for a client | ✅ Frontend |
| 28 | `/api/client/instances/<instance_id>/pricing` | GET | Get current pricing for instance | ✅ Frontend |
| 29 | `/api/client/instances/<instance_id>/metrics` | GET | Get runtime metrics for instance | ✅ Frontend |
| 30 | `/api/client/instances/<instance_id>/price-history` | GET | Get historical spot pricing data | ✅ Frontend |
| 31 | `/api/client/instances/<instance_id>/available-options` | GET | Get available switching options | ✅ Frontend |
| 32 | `/api/client/instances/<instance_id>/force-switch` | POST | Manually force instance switch | ✅ Frontend |
| 33 | `/api/client/pricing-history` | GET | Get pricing history across pools | ⚠️ Not Used |
| **CLIENT - REPLICAS** |
| 34 | `/api/client/<client_id>/replicas` | GET | List replicas for a client | ✅ Frontend |
| **CLIENT - SAVINGS & ANALYTICS** |
| 35 | `/api/client/<client_id>/savings` | GET | Get savings data for charts | ✅ Frontend |
| 36 | `/api/client/<client_id>/switch-history` | GET | Get switch history | ✅ Frontend |
| 37 | `/api/client/<client_id>/stats/charts` | GET | Get chart data for overview | ✅ Frontend |
| **CLIENT - EXPORTS** |
| 38 | `/api/client/<client_id>/export/savings` | GET | Export savings as CSV | ✅ Frontend |
| 39 | `/api/client/<client_id>/export/switch-history` | GET | Export switch history as CSV | ✅ Frontend |
| **AGENTS - REGISTRATION & HEARTBEAT** |
| 40 | `/api/agents/register` | POST | Register new agent with central server | 🤖 Agent Only |
| 41 | `/api/agents/<agent_id>/heartbeat` | POST | Agent heartbeat (every 30-60s) | 🤖 Agent Only |
| 42 | `/api/agents/<agent_id>/config` | GET | Get agent configuration | 🤖 Agent Only |
| **AGENTS - DECISION ENGINE** |
| 43 | `/api/agents/<agent_id>/decide` | POST | Submit state to decision engine | 🤖 Agent Only |
| 44 | `/api/agents/<agent_id>/switch-recommendation` | GET | Get ML-based switch recommendation | 🤖 Agent Only |
| 45 | `/api/agents/<agent_id>/issue-switch-command` | POST | Issue switch command (if auto-switch ON) | 🤖 Agent Only |
| **AGENTS - COMMANDS** |
| 46 | `/api/agents/<agent_id>/pending-commands` | GET | Get pending commands to execute | 🤖 Agent Only |
| 47 | `/api/agents/<agent_id>/commands/<command_id>/executed` | POST | Report command execution status | 🤖 Agent Only |
| **AGENTS - REPORTING** |
| 48 | `/api/agents/<agent_id>/pricing-report` | POST | Report current spot pricing data | 🤖 Agent Only |
| 49 | `/api/agents/<agent_id>/switch-report` | POST | Report switch completion (updates savings) | 🤖 Agent Only |
| 50 | `/api/agents/<agent_id>/termination-report` | POST | Report instance termination | 🤖 Agent Only |
| 51 | `/api/agents/<agent_id>/cleanup-report` | POST | Report cleanup operations | 🤖 Agent Only |
| **AGENTS - TERMINATION & EMERGENCY** |
| 52 | `/api/agents/<agent_id>/termination` | POST | Report termination completion | 🤖 Agent Only |
| 53 | `/api/agents/<agent_id>/rebalance-recommendation` | POST | Report AWS rebalance recommendation | 🤖 Agent Only |
| 54 | `/api/agents/<agent_id>/create-emergency-replica` | POST | Create emergency replica (bypasses settings) | 🤖 Agent Only |
| 55 | `/api/agents/<agent_id>/termination-imminent` | POST | Handle 2-minute termination warning | 🤖 Agent Only |
| 56 | `/api/agents/<agent_id>/instances-to-terminate` | GET | Get instances ready for termination | 🤖 Agent Only |
| **AGENTS - REPLICAS** |
| 57 | `/api/agents/<agent_id>/replica-config` | GET | Get replica configuration | 🤖 Agent Only |
| 58 | `/api/agents/<agent_id>/replicas` | GET | List replicas for agent | 🤖 Agent Only |
| 59 | `/api/agents/<agent_id>/replicas` | POST | Create new replica | 🔄 Frontend + Agent |
| 60 | `/api/agents/<agent_id>/replicas/<replica_id>` | PUT | Update replica metadata | 🤖 Agent Only |
| 61 | `/api/agents/<agent_id>/replicas/<replica_id>` | DELETE | Delete replica | ✅ Frontend |
| 62 | `/api/agents/<agent_id>/replicas/<replica_id>/promote` | POST | Promote replica to primary | ✅ Frontend |
| 63 | `/api/agents/<agent_id>/replicas/<replica_id>/status` | POST | Update replica status | 🤖 Agent Only |
| 64 | `/api/agents/<agent_id>/replicas/<replica_id>/sync-status` | POST | Update replica sync progress | 🤖 Agent Only |
| **NOTIFICATIONS** |
| 65 | `/api/notifications` | GET | Get notifications | ✅ Frontend |
| 66 | `/api/notifications/<notif_id>/mark-read` | POST | Mark notification as read | ✅ Frontend |
| 67 | `/api/notifications/mark-all-read` | POST | Mark all notifications as read | ✅ Frontend |
| **HEALTH** |
| 68 | `/health` | GET | Health check endpoint | ✅ Frontend |

---

## Usage Legend

| Symbol | Meaning | Count |
|--------|---------|-------|
| ✅ Frontend | Used by frontend React application | 44 endpoints |
| 🤖 Agent Only | Used only by monitoring agents | 22 endpoints |
| 🔄 Frontend + Agent | Used by both frontend and agents | 1 endpoint |
| ⚠️ Not Used | Created but not currently used | 2 endpoints |

---

## Key Findings

### 1. **Why the Count Changed**
- **Initial error**: Counted only non-indented `@app.route` = 59
- **Missed**: 7 dynamically registered replica management endpoints (indented in backend.py)
- **Plus**: 2 methods on same paths (GET/POST on `/api/agents/<agent_id>/replicas`)
- **Actual total**: **66 unique paths = 68 total endpoints**

### 2. **Frontend Actually Uses 44 Endpoints**
The frontend calls:
- All admin endpoints (17)
- Client management endpoints (13)
- Instance management (6)
- Agent configuration (4)
- Replica operations (2: delete, promote)
- Notifications (3)
- Health check (1)

### 3. **Agent-Only Endpoints: 22**
These are never called by the frontend:
- Agent registration & heartbeat
- Decision engine interactions
- All reporting endpoints (pricing, switch, cleanup, termination)
- Command polling & execution
- Emergency handling

### 4. **Unused Endpoints: 2**
- `/api/client/validate` - Token validation (not currently used)
- `/api/client/agents/<agent_id>/settings` - Legacy settings endpoint (superseded by `/config`)
- `/api/client/pricing-history` - General pricing history (not wired up in UI)

### 5. **Critical Endpoints (Emergency Bypass)**
These 2 endpoints bypass ALL settings and ML models:
- `/api/agents/<agent_id>/create-emergency-replica` (bypasses auto_switch, manual_replica)
- `/api/agents/<agent_id>/termination-imminent` (2-minute failover, <15s response)

---

## Savings Calculation Endpoint

**Key Endpoint:** `/api/agents/<agent_id>/switch-report` (POST)

This is where savings are calculated and accumulated:
```python
# Backend calculation (line 1229-1334 in backend.py):
savings_impact_per_hour = old_price - new_price

# Add to cumulative total (multiply by 24 for daily estimate):
UPDATE clients
SET total_savings = total_savings + (savings_impact * 24)
WHERE id = client_id
```

**Data Flow:**
1. Agent completes switch
2. Calls `/api/agents/<agent_id>/switch-report` with pricing data
3. Backend calculates `savings_impact = old_price - new_price`
4. Multiplies by 24 (daily estimate)
5. Adds to `clients.total_savings` field
6. Frontend displays accumulated total

---

## Summary

- **Total Endpoints**: 66 unique paths (68 including method variations)
- **Frontend Used**: 44 endpoints (65% of total)
- **Agent Only**: 22 endpoints (32% of total)
- **Shared**: 1 endpoint (1.5% of total)
- **Unused**: 2 endpoints (3% of total)

All endpoints are RESTful, JSON-based, and follow consistent error handling patterns. Emergency endpoints prioritize safety over configuration.
