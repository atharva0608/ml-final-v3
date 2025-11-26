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

## API Endpoints by Category

### 1. Admin Overview & Statistics

#### `GET /api/admin/stats`
Returns global statistics across all clients including total clients, instances, agents, savings, and active/terminated instance counts. Used by the admin dashboard overview.

#### `GET /api/admin/clients`
Retrieves a list of all registered clients with their metadata (name, email, creation date, agent counts, instance counts). Powers the All Clients page.

#### `GET /api/admin/clients/growth?days={days}`
Fetches client growth chart data over the specified number of days (default 30). Returns time-series data for visualizing client acquisition trends.

#### `GET /api/admin/activity`
Returns recent activity log across all clients, including switches, replica operations, agent status changes, and configuration updates. Used for the admin activity log page.

#### `GET /api/admin/system-health`
Provides comprehensive system health metrics including database connectivity, agent health distribution, decision engine status, background job status, and system resource utilization.

#### `GET /api/admin/instances?status={status}&client_id={client_id}`
Fetches all instances across all clients with optional filtering by status (running, terminated, creating, etc.) and client. Powers the global instances view.

#### `GET /api/admin/agents?status={status}&client_id={client_id}`
Retrieves all agents across all clients with optional filtering by online/offline status and client association. Used in the All Agents page.

---

### 2. Client Management

#### `POST /api/admin/clients/create`
**Body:** `{ "name": "Client Name", "email": "client@example.com" }`
Creates a new client account and generates a unique authentication token. Returns the client ID and token for agent registration.

#### `DELETE /api/admin/clients/{client_id}`
Permanently deletes a client and all associated agents, instances, replicas, and historical data. Requires confirmation in the frontend modal.

#### `POST /api/admin/clients/{client_id}/regenerate-token`
Generates a new authentication token for the client, invalidating the old token. Used when token security is compromised.

#### `GET /api/admin/clients/{client_id}/token`
Retrieves the current authentication token for a client. Used by the "View Token" modal in the admin interface.

#### `GET /api/client/validate`
Validates a client authentication token. Used during client dashboard initialization to verify access credentials.

#### `GET /api/client/{client_id}`
Fetches detailed information about a specific client including settings, statistics, and current status. Powers the client detail view.

---

### 3. Agent Management

#### `POST /api/agents/register`
**Body:** `{ "token": "client_token", "agent_name": "Agent Name", "region": "us-east-1", ... }`
Registers a new agent with the central server. Called by agent startup scripts. Returns agent ID and configuration.

#### `POST /api/agents/{agent_id}/heartbeat`
**Body:** `{ "timestamp": "2024-11-26T10:00:00Z", "status": "online", ... }`
Sent periodically by agents (every 30-60 seconds) to signal they are alive and operational. Updates last_seen timestamp.

#### `GET /api/agents/{agent_id}/config`
Retrieves the current configuration for an agent including auto-switching settings, manual replica mode, terminate wait minutes, and emergency fallback configuration.

#### `POST /api/client/agents/{agent_id}/toggle-enabled`
**Body:** `{ "enabled": true }`
Enables or disables an agent. When disabled, the agent continues monitoring but the backend stops issuing switch commands. Used by the agent card toggle in the UI.

#### `POST /api/client/agents/{agent_id}/settings`
**Body:** `{ "setting_name": "value", ... }`
Updates various agent settings. Legacy endpoint, mostly superseded by the config endpoint.

#### `POST /api/client/agents/{agent_id}/config`
**Body:** `{ "autoSwitchEnabled": true, "manualReplicaEnabled": false, "autoTerminateEnabled": true, "terminateWaitMinutes": 5 }`
Updates agent configuration including auto-switching, manual replica management, auto-termination, and termination wait time. Used by the Agent Config Modal.

#### `DELETE /api/client/agents/{agent_id}`
Deletes an agent and marks all its instances as offline. Triggers cleanup scripts on the client side. Used by the "Delete Agent" button in the agent card.

#### `GET /api/client/{client_id}/agents`
Retrieves all agents associated with a client, including their online/offline status, last heartbeat, configuration settings, and monitored instance counts.

#### `GET /api/client/{client_id}/agents/decisions`
Fetches recent decision engine outputs for all agents of a client. Shows ML recommendations, confidence scores, and whether recommendations were executed. Used in the Agent Decisions tab.

#### `GET /api/client/{client_id}/agents/history`
Returns the full agent history including deleted agents with timestamps, lifecycle events, and configuration changes over time.

---

### 4. Instance Management

#### `GET /api/client/{client_id}/instances?status={status}&agent_id={agent_id}`
Retrieves all instances for a client with optional filtering by status (running, terminated, zombie) and agent. Powers the Instances tab with both active and terminated sections.

#### `GET /api/client/instances/{instance_id}/pricing`
Fetches current pricing information for an instance including current spot price, on-demand price, pool information, and savings calculations.

#### `GET /api/client/instances/{instance_id}/metrics`
Returns runtime metrics for an instance such as uptime, CPU/memory utilization, network statistics, and cost accumulation.

#### `GET /api/client/instances/{instance_id}/price-history?days={days}&interval={interval}`
Retrieves historical spot pricing data for an instance's type and pools over the specified time range. Used to populate the pricing chart in the "Manage Instances" modal. Supports intervals like 'hour', 'day'.

#### `GET /api/client/instances/{instance_id}/available-options`
Returns available switching options for an instance including all spot pools (with current prices, availability zones, and stability indicators) and on-demand option. Used by the "Manage Instances" pricing modal.

#### `POST /api/client/instances/{instance_id}/force-switch`
**Body:** `{ "target_pool": "pool_name", "target_type": "spot|on-demand", "auto_terminate": true }`
Manually forces a switch from the current instance to a specified pool or on-demand. Validates that only primaries can be switched. Used by the "Switch" buttons in the Manage Instances modal.

---

### 5. Replica Management

#### `GET /api/client/{client_id}/replicas`
Fetches all replicas associated with a client's instances, including their current status (creating, ready, promoting, deleting), sync status, pool information, and parent primary instance.

#### `GET /api/agents/{agent_id}/replicas`
Returns replicas managed by a specific agent with detailed status information.

#### `POST /api/agents/{agent_id}/replicas`
**Body:** `{ "target_pool": "pool_name", "instance_type": "t3.medium", ... }`
Creates a new replica for the agent's primary instance in the specified pool. Used by the "Create Replica" button in the Replicas tab and manual replica mode.

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/promote`
**Body:** `{ "auto_terminate_old_primary": true, "create_new_replica": false }`
Promotes a replica to become the new primary. The old primary becomes terminated or zombie based on auto-termination settings. Used by the "Switch to Primary" button in the Replicas view.

#### `DELETE /api/agents/{agent_id}/replicas/{replica_id}`
Deletes a replica instance. If manual replica mode is enabled, a new replica is automatically created after deletion. Used by the "Delete Replica" button.

#### `PUT /api/agents/{agent_id}/replicas/{replica_id}`
Updates replica metadata or configuration.

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/status`
Updates the replica's operational status (syncing, ready, error, etc.). Called by agents during replica lifecycle.

#### `POST /api/agents/{agent_id}/replicas/{replica_id}/sync-status`
**Body:** `{ "sync_progress": 85, "sync_state": "syncing", "estimated_completion": "2024-11-26T11:00:00Z" }`
Updates the replication sync progress. Used to show real-time sync status in the Replicas view.

---

### 6. Emergency & Advanced Operations

#### `POST /api/agents/{agent_id}/create-emergency-replica`
**Body:** `{ "reason": "rebalance_recommendation|termination_notice", "notice_time": "2024-11-26T10:00:00Z" }`
Creates an emergency replica in response to AWS rebalance recommendation or termination notice. **Bypasses all settings** including manual replica mode and auto-switching. Always executes as a safety mechanism.

#### `POST /api/agents/{agent_id}/termination-imminent`
**Body:** `{ "instance_id": "i-1234567890abcdef0", "termination_time": "2024-11-26T10:02:00Z" }`
Handles the 2-minute termination warning from AWS. Immediately promotes existing replica to primary if available, completing failover in <15 seconds. **Bypasses all settings and ML models**. Works even if decision engine is offline.

#### `POST /api/agents/{agent_id}/rebalance-recommendation`
**Body:** `{ "instance_id": "i-1234567890abcdef0", "recommendation_time": "2024-11-26T10:00:00Z" }`
Reports AWS rebalance recommendation (early warning of potential termination). Triggers creation of emergency replica if one doesn't exist.

#### `POST /api/agents/{agent_id}/termination`
**Body:** `{ "instance_id": "i-1234567890abcdef0", "reason": "manual|system|aws_notice", "timestamp": "2024-11-26T10:00:00Z" }`
Reports instance termination completion. Updates instance status to terminated and records termination details in history.

---

### 7. Decision Engine & ML Integration

#### `GET /api/agents/{agent_id}/switch-recommendation`
Returns the ML-based recommendation for switching pools. Shows what the decision engine suggests regardless of auto-switching settings. Response includes `will_auto_execute` flag based on auto_switch_enabled.

#### `POST /api/agents/{agent_id}/issue-switch-command`
**Body:** `{ "target_pool": "pool_name", "confidence": 0.85, "reason": "cost_optimization" }`
Issues a switch command based on ML recommendation. **Checks auto_switch_enabled** before creating command. If auto-switching is OFF, returns 403 error. If ON, creates command in the commands table for agent to execute.

#### `POST /api/agents/{agent_id}/decide`
**Body:** `{ "current_state": {...}, "pricing_data": {...}, "metrics": {...} }`
Submits current instance state, pricing, and metrics to the decision engine for analysis. Returns recommendation with confidence score. Called periodically by agents.

#### `GET /api/agents/{agent_id}/replica-config`
Retrieves replica configuration including whether manual replica mode is enabled, preferred replica pools, and sync requirements.

#### `POST /api/admin/decision-engine/upload`
**Body:** Multipart form data with Python files (.py, .pkl, .joblib)
Uploads decision engine Python files. Triggers automatic backend reload to activate the new decision engine code.

#### `POST /api/admin/ml-models/upload`
**Body:** Multipart form data with model files (.pkl, .joblib, .h5, .pb, .pth, .onnx, .pt)
Uploads ML model files to the server. Creates a new model session with timestamp. Used by the admin ML model upload interface.

#### `POST /api/admin/ml-models/activate`
**Body:** `{ "sessionId": "20241126_100000" }`
Activates a previously uploaded ML model session. Triggers backend restart to load the new models (RED RESTART button in UI).

#### `POST /api/admin/ml-models/fallback`
Falls back to the previous ML model session if the current models are broken or performing poorly. Reloads the last known good model state.

#### `GET /api/admin/ml-models/sessions`
Retrieves list of all ML model upload sessions with timestamps, file lists, and activation status. Used in the Client Models tab.

---

### 8. Command & Execution Tracking

#### `GET /api/agents/{agent_id}/pending-commands`
Fetches pending commands for an agent to execute. Agents poll this endpoint regularly (every 30-60 seconds) to receive switch, replica, or termination commands from the backend.

#### `POST /api/agents/{agent_id}/commands/{command_id}/executed`
**Body:** `{ "status": "success|failed", "execution_time": "2024-11-26T10:05:00Z", "error": "error message if failed" }`
Confirms command execution by the agent. Updates command status and records execution details for audit trail.

---

### 9. Reporting & Telemetry

#### `POST /api/agents/{agent_id}/pricing-report`
**Body:** `{ "instance_id": "i-1234567890abcdef0", "spot_prices": [{...}], "on_demand_price": 0.05, ... }`
Submits current spot pricing data from AWS. Used to populate pricing history and charts. Called periodically by agents (every 5-15 minutes).

#### `POST /api/agents/{agent_id}/switch-report`
**Body:** `{ "from_instance_id": "i-123...", "to_instance_id": "i-456...", "downtime_seconds": 12, "trigger": "automatic|manual|emergency", ... }`
Reports completion of a switch operation with downtime measurement, trigger type, and context. Stored in switch history for analytics.

#### `POST /api/agents/{agent_id}/cleanup-report`
**Body:** `{ "instances_cleaned": ["i-123...", "i-456..."], "resources_freed": {...}, ... }`
Reports cleanup operations performed by the agent such as terminating zombie instances or removing old replicas.

#### `GET /api/agents/{agent_id}/instances-to-terminate`
Returns list of instances that should be terminated by the agent based on auto-termination settings and zombie cleanup policies.

---

### 10. Savings & Analytics

#### `GET /api/client/{client_id}/savings?range={range}`
**Params:** `range` = 'daily' | 'weekly' | 'monthly' | 'yearly'
Calculates savings compared to on-demand baseline for the specified time range. Returns total savings, percentage, and breakdown by instance. Powers the Savings view.

#### `GET /api/client/{client_id}/switch-history?instance_id={instance_id}`
Retrieves switch history for a client with optional filtering by instance. Shows all switch events with timestamps, from/to pools, trigger types, downtime, and configuration context. Used in the History view.

#### `GET /api/client/{client_id}/stats/charts`
Fetches chart data for the client detail view including instance count over time, savings trends, switch frequency, and downtime distribution.

#### `GET /api/client/pricing-history?client_id={client_id}&instance_type={type}&days={days}`
Returns historical pricing data for specific instance types across multiple pools and regions. Used for pricing trend analysis and forecasting.

---

### 11. Export & Download

#### `GET /api/client/{client_id}/export/savings`
Generates and downloads a CSV export of savings data for the client. Opens in new browser tab.

#### `GET /api/client/{client_id}/export/switch-history`
Generates and downloads a CSV export of switch history for the client. Opens in new browser tab.

#### `GET /api/admin/export/global-stats`
Generates and downloads a comprehensive CSV export of global statistics across all clients. Admin-only endpoint.

---

### 12. Notifications

#### `GET /api/notifications?client_id={client_id}&limit={limit}`
Fetches notifications for a client (or all clients if admin) with optional limit. Returns unread count and recent notification list. Used by the notification panel.

#### `POST /api/notifications/{notif_id}/mark-read`
Marks a specific notification as read. Called when user clicks on a notification.

#### `POST /api/notifications/mark-all-read`
**Body:** `{ "client_id": "optional_client_id" }`
Marks all notifications as read for a client or globally (if admin). Used by the "Mark All as Read" button.

---

### 13. Health & Monitoring

#### `GET /health`
Simple health check endpoint that returns 200 OK if the server is running. Used for load balancer health checks and monitoring systems.

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

7. **Real-time Updates**: The backend supports event streaming or websocket connections (implementation details in backend) to push live updates to the frontend for instance status, agent connectivity, and notifications.

8. **Validation**: All endpoints perform input validation and return appropriate 400 Bad Request errors with descriptive messages for invalid inputs.

---

## Summary

The central server API provides **65 distinct endpoints** organized into 13 functional categories. These endpoints enable comprehensive management of:
- Multi-client infrastructure with isolation
- Agent registration, lifecycle, and configuration
- Instance and replica orchestration
- Emergency failover and safety mechanisms
- ML-driven decision making with manual override capability
- Real-time monitoring and notifications
- Analytics, savings calculations, and historical reporting
- Administrative controls and system health monitoring

The API design prioritizes **safety** (emergency bypass mechanisms), **flexibility** (manual overrides for automation), **visibility** (comprehensive telemetry and reporting), and **scalability** (connection pooling, background jobs, efficient queries).
