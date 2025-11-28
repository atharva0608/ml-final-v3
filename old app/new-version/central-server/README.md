# AWS Spot Optimizer - Backend v6.0 (Production-Grade)

**Complete rewrite aligned with operational runbook requirements**

## 🎯 Overview

This is a production-grade central server for AWS Spot Instance optimization with ML-driven decision making, emergency handling, and strict consistency guarantees. The system manages PRIMARY/REPLICA/ZOMBIE instance lifecycle with real-time monitoring and comprehensive data pipelines.

### Key Features

✅ **Three-Tier Instance State Machine** - PRIMARY/REPLICA/ZOMBIE/TERMINATED with atomic transitions
✅ **Emergency Flow Orchestration** - Rebalance (2-min) and termination (immediate) notice handling
✅ **Optimistic Locking** - Concurrent-safe state changes with version control
✅ **Idempotency Support** - Request ID-based duplicate prevention
✅ **Three-Tier Data Pipeline** - Staging → Consolidated → Canonical
✅ **ML Model Interface** - Pluggable decision engine with validation
✅ **Comprehensive Audit Trails** - Pre/post state tracking with user attribution
✅ **Real-Time Metrics** - Downtime analytics, emergency events, consolidation jobs

---

## 📁 Architecture

```
backend_v5/
├── backend.py                    # Main application entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
│
├── config/                       # Configuration
│   ├── __init__.py
│   └── settings.py               # All environment settings
│
├── core/                         # Core Infrastructure
│   ├── __init__.py
│   ├── database.py               # Connection pool + optimistic locking
│   ├── auth.py                   # Authentication decorators
│   ├── utils.py                  # Utility functions
│   ├── validation.py             # Marshmallow schemas
│   ├── idempotency.py           # ⭐ NEW: Request ID duplicate prevention
│   ├── emergency.py             # ⭐ NEW: Emergency flow orchestration
│   └── ml_interface.py          # ⭐ NEW: ML model integration
│
├── routes/                       # API Endpoints (12 modules, 78 endpoints)
│   ├── __init__.py
│   ├── health.py                 # Health check
│   ├── admin.py                  # Admin operations
│   ├── clients.py                # Client management
│   ├── agents.py                 # Agent operations
│   ├── instances.py              # Instance management
│   ├── replicas.py               # Replica operations
│   ├── emergency.py              # Emergency handling
│   ├── decisions.py              # ML/Decision engine
│   ├── commands.py               # Command orchestration
│   ├── reporting.py              # Telemetry & reporting
│   ├── analytics.py              # Analytics & exports
│   └── notifications.py          # Notifications
│
├── jobs/                         # ⭐ NEW: Background Jobs
│   ├── __init__.py
│   └── pricing_consolidation.py # 12-hour data pipeline
│
├── database/                     # ⭐ NEW: Database Schema
│   └── schema.sql                # Complete v6.0 schema
│
├── frontend/                     # ⭐ NEW: Frontend Components
│   └── src/
│       ├── services/
│       │   └── apiClient.js      # Complete API client
│       ├── components/
│       │   ├── cards/
│       │   │   └── DowntimeCard.jsx
│       │   └── emergency/
│       │       └── EmergencyEventAlert.jsx
│       └── config/
│
└── OPERATIONAL_RUNBOOK_IMPLEMENTATION.md  # Full implementation guide
```

---

## 🚀 Quick Start

### 1. Installation

```bash
cd central-server/backend_v5

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your database credentials
```

### 2. Database Setup

```bash
# Create database
mysql -u root -p -e "CREATE DATABASE spot_optimizer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Import schema
mysql -u root -p spot_optimizer < database/schema.sql
```

### 3. Configure Environment

Edit `.env`:

```bash
# Database
DB_HOST=localhost
DB_PASSWORD=your_secure_password
DB_DATABASE=spot_optimizer

# Security
ADMIN_TOKEN=your-secure-admin-token
CORS_ORIGINS=http://localhost:3000

# Application
FLASK_ENV=production
FLASK_DEBUG=False
LOG_LEVEL=INFO
```

### 4. Run the Server

```bash
# Development
python backend.py

# Production (with Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 backend:app
```

### 5. Verify Installation

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
```

---

## 🔥 What's New in v6.0

### Database (Complete Rewrite)

**Three-Tier Pricing Architecture:**
- **Staging** (`spot_price_snapshots`) - Raw data from agents
- **Consolidated** (`pricing_consolidated`) - Deduplicated & interpolated
- **Canonical** (`pricing_canonical`) - ML training data with lifecycle features

**Concurrency Control:**
- Optimistic locking with `version` columns
- Triggers auto-increment version on UPDATE
- Stored procedure `promote_instance_to_primary()` for atomic role changes

**Idempotency:**
- `request_id` column in commands, switches, replicas
- Unique constraints prevent duplicate executions
- Cached results for retries

**Emergency Tracking:**
- `notice_status` ENUM ('none', 'rebalance', 'termination')
- `notice_deadline`, `fastest_boot_pool_id` fields
- Emergency replica tracking with boot time metrics

**ML Model Interface:**
- `ml_models` table - Model registry with activation
- `ml_decisions` table - Decision log with execution tracking
- `ml_training_datasets` table - Dataset management

**Audit Fields:**
- `pre_state` and `post_state` JSON columns
- `user_id` for manual actions
- `lifecycle_event_type` for polymorphic events

### Core Modules

**core/idempotency.py:**
```python
@require_idempotency_key  # Decorator for endpoints
def my_endpoint():
    request_id = request.request_id  # Access idempotency key
    ...
```

**core/emergency.py:**
- `handle_rebalance_notice()` - 2-minute window handling
- `handle_termination_notice()` - Immediate failover
- `create_emergency_replica()` - Fastest pool selection
- `promote_replica()` - Atomic promotion with health check

**core/ml_interface.py:**
- `invoke_ml_decision()` - ML engine invocation with validation
- `register_ml_model()` - Add model to registry
- `activate_ml_model()` - Activate for production
- `get_model_performance_metrics()` - Monitor model performance

**core/database.py Enhancements:**
- `execute_with_optimistic_lock()` - Version-based updates
- `execute_transaction()` - Multi-operation atomicity
- `call_stored_procedure()` - Database procedures

### Background Jobs

**jobs/pricing_consolidation.py:**
- Runs every 12 hours via APScheduler
- Deduplicates pricing (PRIMARY precedence over REPLICA)
- Interpolates gaps (linear interpolation)
- Integrates backfilled data from cloud API
- Updates canonical layer for ML training

### Frontend Components

**components/cards/DowntimeCard.jsx:**
- Switch downtime analytics with p95, avg, min, max
- 24-hour rolling window
- Success rate tracking
- Trend indicators

**components/emergency/EmergencyEventAlert.jsx:**
- Real-time emergency event display
- Countdown timer for termination
- Emergency replica status
- Action timeline

**services/apiClient.js:**
- Complete API client with all 78 endpoints
- Idempotency key generation
- Emergency flow endpoints
- Operational metrics endpoints

---

## 📊 Database Schema Highlights

### Instance State Machine

```
PRIMARY → (on failover) → ZOMBIE
   ↓
REPLICA → (promoted) → PRIMARY
```

**Invariants:**
- Exactly one PRIMARY per agent (enforced by stored procedure)
- Manual replica mode and auto-switch are mutually exclusive
- New agent installation always generates new agent_id

### Pricing Data Flow

```
Agents → spot_price_snapshots (Staging)
           ↓ (12-hour job)
       pricing_consolidated (Deduplicated + Interpolated)
           ↓
       pricing_canonical (ML Training with Lifecycle Features)
```

---

## 🔐 Security Features

### Authentication

- **Admin endpoints**: `Authorization: Bearer <admin_token>`
- **Client endpoints**: `Authorization: Bearer <client_token>`
- **Token validation**: Database lookup with status check

### Security Best Practices

- SQL injection protection (parameterized queries)
- Input validation (Marshmallow schemas)
- CORS configuration
- Optimistic locking for race conditions
- Idempotency for retry safety
- Comprehensive audit logging

---

## 📝 API Endpoints (78 Total)

### Emergency Flow (NEW)
- `POST /api/agents/<id>/rebalance-notice` - Report rebalance recommendation
- `POST /api/agents/<id>/termination-notice` - Report termination notice
- `GET /api/agents/<id>/emergency-status` - Get emergency status

### Operational Metrics (NEW)
- `GET /api/admin/metrics/operational` - Operational dashboard metrics
- `GET /api/admin/consolidation-jobs` - Data consolidation job status
- `GET /api/admin/emergency-events` - Emergency event summary
- `GET /api/client/<id>/analytics/downtime` - Downtime analytics

### ML Model Interface (NEW)
- `POST /api/admin/ml-models/upload` - Upload ML model
- `POST /api/admin/ml-models/activate` - Activate model
- `GET /api/admin/ml-models/sessions` - List model sessions

### Existing Endpoints (All Preserved)
- Health & Root (2)
- Admin Operations (14)
- Client Management (3)
- Agent Operations (12)
- Instance Management (9)
- Replica Operations (1)
- Decision Engine (5)
- Commands (2)
- Reporting & Telemetry (4)
- Analytics & Exports (6)
- Notifications (3)
- Advanced Features (3)
- Real-Time (1)

---

## 🧪 Testing

### Test Emergency Flow

```bash
# Simulate rebalance notice
curl -X POST http://localhost:5000/api/agents/<agent_id>/rebalance-notice \
  -H "Authorization: Bearer <client_token>" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: $(uuidgen)" \
  -d '{"notice_time": "2024-11-26T12:00:00"}'

# Check emergency status
curl http://localhost:5000/api/agents/<agent_id>/emergency-status \
  -H "Authorization: Bearer <client_token>"
```

### Test Idempotency

```bash
# First request
curl -X POST http://localhost:5000/api/agents/<agent_id>/issue-switch-command \
  -H "Authorization: Bearer <client_token>" \
  -H "X-Request-ID: test-idempotency-123" \
  -d '{"target_pool": "pool-123"}'

# Retry with same request ID (should return cached result)
curl -X POST http://localhost:5000/api/agents/<agent_id>/issue-switch-command \
  -H "Authorization: Bearer <client_token>" \
  -H "X-Request-ID: test-idempotency-123" \
  -d '{"target_pool": "pool-123"}'
```

### Test Optimistic Locking

```python
# Concurrent updates will be serialized
from core.database import execute_with_optimistic_lock

# Get current version
instance = execute_query("SELECT version FROM instances WHERE id = %s", (instance_id,), fetch_one=True)

# Try to update with version check
success = execute_with_optimistic_lock(
    'instances',
    instance_id,
    "UPDATE instances SET status = %s WHERE id = %s",
    ('running_primary', instance_id),
    instance['version']
)

if not success:
    # Version conflict - retry or abort
    pass
```

---

## 🐛 Debugging

### Enable Debug Logging

```bash
LOG_LEVEL=DEBUG python backend.py
```

### Check Logs

```bash
tail -f logs/backend_v5.log    # All logs
tail -f logs/error.log          # Errors only
```

### Common Issues

**Database Connection Fails:**
- Check MySQL is running: `mysql -u root -p`
- Verify credentials in `.env`

**Optimistic Lock Conflicts:**
- Normal under high concurrency
- Check logs for conflict patterns
- May need to increase retry logic

**Emergency Replica Not Created:**
- Check `fastest_boot_pool_id` is set
- Verify sufficient capacity in pools
- Review `consolidation_jobs` table

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_DEBUG=False`
- [ ] Use strong `ADMIN_TOKEN` (64+ chars)
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Use HTTPS (reverse proxy with nginx)
- [ ] Set up monitoring (health check endpoint)
- [ ] Configure gunicorn workers (4-8 workers)
- [ ] Set up APScheduler for consolidation jobs

### Gunicorn Configuration

```bash
gunicorn -w 4 \
  -b 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  backend:app
```

### Systemd Service

```ini
[Unit]
Description=AWS Spot Optimizer Backend v6.0
After=network.target mysql.service

[Service]
Type=simple
User=optimizer
WorkingDirectory=/opt/spot-optimizer/backend_v5
Environment="PATH=/opt/spot-optimizer/venv/bin"
ExecStart=/opt/spot-optimizer/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 backend:app
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 📈 Success Criteria

| Metric | Target | Status |
|--------|--------|--------|
| Agent heartbeat miss rate | <5% | ✅ Monitored via v_agent_health_summary |
| Manual switch downtime (p95) | <10s | ✅ Tracked in switches.downtime_seconds |
| Emergency promotion window | 99% within 2min | ⏳ Requires deployment metrics |
| Pricing chart update latency | <30s | ⏳ Requires SSE integration |
| ML decision latency | <500ms | ⏳ Requires ML model deployment |
| Zombie cleanup | 30-day auto | ⏳ Requires scheduled job |

---

## 📚 Documentation

- **OPERATIONAL_RUNBOOK_IMPLEMENTATION.md** - Complete implementation guide
- **routes/AGENTS_DOCUMENTATION.md** - Agent endpoints documentation
- **database/schema.sql** - Complete database schema with comments
- **frontend/src/services/apiClient.js** - API client reference

---

## 🔄 Migration from Old Backend

If migrating from monolithic `backend.py`:

1. **Database Schema**: Import `database/schema.sql` (adds new tables, preserves old)
2. **Environment Variables**: Same variables, copy from old `.env`
3. **API Endpoints**: All endpoints preserved (+ 15 new emergency/metrics endpoints)
4. **Agents**: No changes required on agent side
5. **Frontend**: Update API client to use new endpoints

### Side-by-Side Testing

```bash
# Run old backend on port 5000
python backend/backend.py

# Run new backend on port 5001
FLASK_PORT=5001 python backend_v5/backend.py
```

---

## 🤝 Contributing

### Adding a New Endpoint

1. Choose appropriate route module (or create new)
2. Add endpoint with decorators:

```python
from core.idempotency import require_idempotency_key

@module_bp.route('/new-endpoint', methods=['POST'])
@require_client_auth
@require_idempotency_key
def new_endpoint(authenticated_client_id=None):
    try:
        request_id = request.request_id  # Access idempotency key
        # Implementation
        return jsonify(success_response(data))
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify(*error_response("Error message", "ERROR_CODE", 500))
```

3. Test endpoint
4. Update this README

---

## 📞 Support

For issues, questions, or contributions:
- Check logs: `logs/error.log`
- Review this README
- Check operational runbook: `OPERATIONAL_RUNBOOK_IMPLEMENTATION.md`
- Verify database schema: `database/schema.sql`

---

## 📄 License

Proprietary - AWS Spot Optimizer Team

---

**Version**: 6.0
**Last Updated**: 2024-11-26
**Maintained By**: AWS Spot Optimizer Team
**Aligned With**: Operational Runbook Requirements v1.0
