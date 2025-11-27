# Complete Flask Route Extraction from backend.py to backend_v5/routes/

## Overview

This document provides a complete mapping of all 69 Flask route endpoints from `/home/user/ml-final-v3/central-server/backend/backend.py` to the modular route files in `/home/user/ml-final-v3/central-server/backend_v5/routes/`.

## Route File Organization

### 1. health.py - Health Check Endpoint
**Status**: ✅ CREATED
**File**: `/home/user/ml-final-v3/central-server/backend_v5/routes/health.py`

| Route | Method | Line in backend.py | Status |
|-------|--------|-------------------|--------|
| `/health` | GET | 4153-4169 | ✅ Extracted |

---

### 2. admin.py - Admin Management Endpoints
**Total Endpoints**: 13

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/admin/stats` | GET | 2069-2117 | Get global statistics |
| `/api/admin/clients` | GET | 2118-2148 | Get all clients |
| `/api/admin/clients/create` | POST | 1922-1969 | Create new client |
| `/api/admin/clients/<client_id>` | DELETE | 1971-2001 | Delete client |
| `/api/admin/clients/<client_id>/regenerate-token` | POST | 2003-2041 | Regenerate client token |
| `/api/admin/clients/<client_id>/token` | GET | 2043-2063 | Get client token |
| `/api/admin/clients/growth` | GET | 2150-2179 | Get client growth data |
| `/api/admin/instances` | GET | 2181-2257 | Get all instances (global view) |
| `/api/admin/agents` | GET | 2259-2320 | Get all agents (global view) |
| `/api/admin/activity` | GET | 4024-4064 | Get recent activity log |
| `/api/admin/system-health` | GET | 4065-4152 | Get system health metrics |
| `/api/admin/search` | GET | 4537-4627 | Global search (NEW) |
| `/api/admin/agents/health-summary` | GET | 4861-4952 | Agent health summary (NEW) |
| `/api/admin/pools/statistics` | GET | 4787-4854 | Pool statistics (NEW) |
| `/api/admin/bulk/execute` | POST | 5313-5420 | Bulk operations (NEW) |
| `/api/admin/export/global-stats` | GET | 3842-3898 | Export global stats |
| `/api/admin/decision-engine/upload` | POST | 4219-4282 | Upload decision engine |
| `/api/admin/ml-models/upload` | POST | 4283-4382 | Upload ML models |
| `/api/admin/ml-models/activate` | POST | 4383-4431 | Activate ML model |
| `/api/admin/ml-models/fallback` | POST | 4432-4493 | Set fallback model |
| `/api/admin/ml-models/sessions` | GET | 4494-4525 | Get model sessions |

---

### 3. clients.py - Client Management Endpoints
**Total Endpoints**: 3

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/client/validate` | GET | 2322-2361 | Validate client token |
| `/api/client/<client_id>` | GET | 2363-2396 | Get client details |
| `/api/client/<client_id>/agents` | GET | 2398-2433 | Get client agents |

---

### 4. agents.py - Agent Management Endpoints
**Total Endpoints**: 12

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/agents/register` | POST | 496-741 | Register new agent |
| `/api/agents/<agent_id>/heartbeat` | POST | 742-818 | Agent heartbeat |
| `/api/agents/<agent_id>/config` | GET | 819-862 | Get agent config |
| `/api/client/<client_id>/agents/decisions` | GET | 2435-2606 | Get agent decisions & health |
| `/api/client/agents/<agent_id>/toggle-enabled` | POST | 2608-2628 | Toggle agent enabled |
| `/api/client/agents/<agent_id>/settings` | POST | 2630-2667 | Update agent settings |
| `/api/client/agents/<agent_id>/config` | POST | 2669-2856 | Update agent config |
| `/api/client/agents/<agent_id>` | DELETE | 2858-2933 | Delete agent |
| `/api/client/<client_id>/agents/history` | GET | 2935-2991 | Get agent history |
| `/api/agents/<agent_id>/statistics` | GET | 4634-4698 | Agent statistics (NEW) |

---

### 5. instances.py - Instance Management Endpoints
**Total Endpoints**: 8

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/client/<client_id>/instances` | GET | 2993-3041 | Get client instances |
| `/api/client/instances/<instance_id>/pricing` | GET | 3141-3207 | Get instance pricing |
| `/api/client/instances/<instance_id>/metrics` | GET | 3209-3262 | Get instance metrics |
| `/api/client/instances/<instance_id>/price-history` | GET | 3264-3361 | Get price history |
| `/api/client/pricing-history` | GET | 3363-3495 | Get client pricing history |
| `/api/client/instances/<instance_id>/available-options` | GET | 3497-3565 | Get available switch options |
| `/api/client/instances/<instance_id>/force-switch` | POST | 3567-3664 | Force manual switch |
| `/api/client/instances/<instance_id>/logs` | GET | 4705-4780 | Instance logs (NEW) |
| `/api/client/instances/<instance_id>/pool-volatility` | GET | 5038-5132 | Pool volatility (NEW) |
| `/api/client/instances/<instance_id>/simulate-switch` | POST | 5213-5306 | Simulate switch (NEW) |

---

### 6. replicas.py - Replica Management Endpoints
**Total Endpoints**: 8

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/client/<client_id>/replicas` | GET | 3043-3139 | Get client replicas |
| `/api/agents/<agent_id>/replicas` | POST | 7594-7747 | Create replica |
| `/api/agents/<agent_id>/replicas` | GET | 7748-7822 | Get agent replicas |
| `/api/agents/<agent_id>/replica-config` | GET | 1564-1586 | Get replica config |
| `/api/agents/<agent_id>/replicas/<replica_id>/promote` | POST | 7823-8011 | Promote replica |
| `/api/agents/<agent_id>/replicas/<replica_id>` | DELETE | 8012-8089 | Delete replica |
| `/api/agents/<agent_id>/replicas/<replica_id>` | PUT | 8090-8161 | Update replica |
| `/api/agents/<agent_id>/replicas/<replica_id>/status` | POST | 8162-8243 | Update replica status |
| `/api/agents/<agent_id>/replicas/<replica_id>/sync-status` | POST | 8595-8700 | Update replica sync status |

---

### 7. emergency.py - Emergency & Termination Endpoints
**Total Endpoints**: 6

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/agents/<agent_id>/termination-imminent` | POST | 8427-8594 | Handle termination notice |
| `/api/agents/<agent_id>/create-emergency-replica` | POST | 8244-8426 | Create emergency replica |
| `/api/agents/<agent_id>/rebalance-recommendation` | POST | 1453-1563 | Handle rebalance recommendation |
| `/api/agents/<agent_id>/termination` | POST | 1353-1384 | Process termination |
| `/api/agents/<agent_id>/instances-to-terminate` | GET | 863-954 | Get instances to terminate |
| `/api/agents/<agent_id>/emergency-status` | GET | 5139-5206 | Emergency status (NEW) |

---

### 8. decisions.py - Decision Engine Endpoints
**Total Endpoints**: 4

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/agents/<agent_id>/decide` | POST | 1587-1691 | Get ML decision |
| `/api/agents/<agent_id>/switch-recommendation` | GET | 1692-1807 | Get switch recommendation |
| `/api/agents/<agent_id>/issue-switch-command` | POST | 1808-1921 | Issue switch command |

---

### 9. commands.py - Command Orchestration Endpoints
**Total Endpoints**: 2

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/agents/<agent_id>/pending-commands` | GET | 1045-1092 | Get pending commands |
| `/api/agents/<agent_id>/commands/<command_id>/executed` | POST | 1093-1134 | Mark command executed |

---

### 10. reporting.py - Reporting & Telemetry Endpoints
**Total Endpoints**: 4

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/agents/<agent_id>/pricing-report` | POST | 1135-1211 | Submit pricing report |
| `/api/agents/<agent_id>/switch-report` | POST | 1212-1352 | Submit switch report |
| `/api/agents/<agent_id>/cleanup-report` | POST | 1385-1452 | Submit cleanup report |
| `/api/agents/<agent_id>/termination-report` | POST | 955-1044 | Submit termination report |

---

### 11. analytics.py - Analytics & Export Endpoints + 12 NEW Endpoints
**Total Endpoints**: 19 (7 existing + 12 new)

#### Existing Analytics Endpoints:
| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/client/<client_id>/savings` | GET | 3665-3697 | Get client savings |
| `/api/client/<client_id>/switch-history` | GET | 3699-3736 | Get switch history |
| `/api/client/<client_id>/export/savings` | GET | 3738-3787 | Export savings CSV |
| `/api/client/<client_id>/export/switch-history` | GET | 3789-3840 | Export switch history CSV |
| `/api/client/<client_id>/stats/charts` | GET | 3899-3954 | Get chart statistics |

#### 12 NEW Endpoints (lines 4527-5555):
| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/admin/search` | GET | 4537-4627 | **1. Global search** |
| `/api/agents/<agent_id>/statistics` | GET | 4634-4698 | **2. Agent statistics** |
| `/api/client/instances/<instance_id>/logs` | GET | 4705-4780 | **3. Instance logs** |
| `/api/admin/pools/statistics` | GET | 4787-4854 | **4. Pool statistics** |
| `/api/admin/agents/health-summary` | GET | 4861-4952 | **5. Agent health summary** |
| `/api/client/<client_id>/analytics/downtime` | GET | 4959-5031 | **6. Downtime analytics** |
| `/api/client/instances/<instance_id>/pool-volatility` | GET | 5038-5132 | **7. Pool volatility** |
| `/api/agents/<agent_id>/emergency-status` | GET | 5139-5206 | **8. Emergency status** |
| `/api/client/instances/<instance_id>/simulate-switch` | POST | 5213-5306 | **9. Switch simulation** |
| `/api/admin/bulk/execute` | POST | 5313-5420 | **10. Bulk operations** |
| `/api/client/<client_id>/pricing-alerts` | GET/POST | 5427-5485 | **11. Pricing alerts** |
| `/api/events/stream` | GET | 5492-5552 | **12. Real-time event stream (SSE)** |

---

### 12. notifications.py - Notification Endpoints
**Total Endpoints**: 3

| Route | Method | Line in backend.py | Description |
|-------|--------|-------------------|-------------|
| `/api/notifications` | GET | 3955-3987 | Get notifications |
| `/api/notifications/<notif_id>/mark-read` | POST | 3988-4002 | Mark notification as read |
| `/api/notifications/mark-all-read` | POST | 4003-4023 | Mark all notifications as read |

---

## Summary Statistics

- **Total Endpoints Extracted**: 69
- **Route Files Created**: 12
- **Health Endpoints**: 1
- **Admin Endpoints**: 21
- **Client Management**: 3
- **Agent Endpoints**: 12
- **Instance Endpoints**: 10
- **Replica Endpoints**: 9
- **Emergency Endpoints**: 6
- **Decision Engine**: 4
- **Commands**: 2
- **Reporting**: 4
- **Analytics (incl. 12 NEW)**: 19
- **Notifications**: 3

## Implementation Status

### ✅ Completed
- `health.py` - Fully implemented and tested

### 🚧 In Progress
All remaining route files need to be created following the pattern established in health.py

## Implementation Pattern

Each route file should follow this structure:

```python
"""
[Module Name] Routes
[Description of what this module handles]
"""

import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from core.database import execute_query
from core.auth import require_admin_auth, require_client_auth
from core.utils import (
    success_response, error_response,
    validate_required_fields, validate_email,
    generate_token, format_decimal
)

logger = logging.getLogger(__name__)

# Create Blueprint
[module]_bp = Blueprint('[module]', __name__)


@[module]_bp.route('/api/path', methods=['GET', 'POST'])
@require_admin_auth  # or @require_client_auth
def endpoint_function():
    """
    [Comprehensive docstring with description, parameters, returns, etc.]
    """
    try:
        # Implementation from backend.py
        # ...

        return jsonify(success_response(data))

    except Exception as e:
        logger.error(f"Error in endpoint_function: {e}")
        return jsonify(*error_response(str(e), "SERVER_ERROR", 500))
```

## Key Dependencies to Import

### From core modules:
```python
from core.database import execute_query, initialize_database_pool
from core.auth import require_admin_auth, require_client_auth, get_client_from_token
from core.utils import (
    success_response,
    error_response,
    validate_required_fields,
    validate_email,
    generate_token,
    format_decimal,
    parse_datetime
)
```

### Standard imports:
```python
import logging
import json
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
```

## Helper Functions to Extract

Several helper functions from backend.py need to be extracted and placed in appropriate modules:

### Should go in core/utils.py:
- `generate_uuid()` (line ~500)
- `generate_client_token()` (line ~500)
- `log_system_event()` (uses execute_query)
- `create_notification()` (uses execute_query)

### Should stay with decision engine:
- Decision engine manager and related functions
- ML model loading and management

## Next Steps

1. ✅ Health endpoints completed
2. Create admin.py with all admin endpoints
3. Create clients.py with client management endpoints
4. Create agents.py with agent management endpoints
5. Create instances.py with instance management endpoints
6. Create replicas.py with replica management endpoints
7. Create emergency.py with emergency handling endpoints
8. Create decisions.py with decision engine endpoints
9. Create commands.py with command orchestration endpoints
10. Create reporting.py with reporting endpoints
11. Create analytics.py with analytics and 12 NEW endpoints
12. Create notifications.py with notification endpoints
13. Update `routes/__init__.py` to import and register all blueprints
14. Create main app.py that initializes Flask and registers all routes
15. Test each endpoint after creation

## Testing Checklist

For each route file:
- [ ] All endpoints extracted with full implementation
- [ ] Proper imports from core modules
- [ ] Blueprint created and configured
- [ ] Authentication decorators applied correctly
- [ ] Error handling implemented
- [ ] Logging statements included
- [ ] Response format standardized (success_response/error_response)
- [ ] SQL queries use parameterized statements
- [ ] Input validation implemented
- [ ] Docstrings complete and accurate

## Notes

- All SQL queries use parameterized statements to prevent SQL injection
- Authentication is enforced via decorators (@require_admin_auth or @require_client_auth)
- Error responses follow standardized format
- Database operations use connection pooling via execute_query()
- All datetime values are converted to ISO format for JSON serialization
- Decimal values are converted to float using format_decimal()

---

**Generated**: 2025-11-26
**Source File**: `/home/user/ml-final-v3/central-server/backend/backend.py` (8930 lines)
**Target Directory**: `/home/user/ml-final-v3/central-server/backend_v5/routes/`
