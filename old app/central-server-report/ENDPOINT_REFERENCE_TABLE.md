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
