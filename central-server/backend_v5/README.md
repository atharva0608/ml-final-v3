# AWS Spot Optimizer - Backend v5.0 (Modular Architecture)

**Production-grade central server with clean modular architecture**

## 📁 Project Structure

```
backend_v5/
├── backend.py              # Main application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── config/                # Configuration module
│   ├── __init__.py
│   └── settings.py        # All environment settings
├── core/                  # Core functionality
│   ├── __init__.py
│   ├── database.py        # MySQL connection pool & query execution
│   ├── auth.py            # Authentication decorators
│   └── utils.py           # Utility functions (validation, formatting, etc.)
├── routes/                # API endpoint modules (12 modules)
│   ├── __init__.py        # Route registration
│   ├── health.py          # Health check (1 endpoint)
│   ├── admin.py           # Admin operations (14 endpoints)
│   ├── clients.py         # Client management (3 endpoints)
│   ├── agents.py          # Agent operations (12 endpoints)
│   ├── instances.py       # Instance management (9 endpoints)
│   ├── replicas.py        # Replica operations (1 endpoint)
│   ├── emergency.py       # Emergency handling (placeholder)
│   ├── decisions.py       # ML/Decision engine (5 endpoints)
│   ├── commands.py        # Command orchestration (2 endpoints)
│   ├── reporting.py       # Telemetry & reporting (4 endpoints)
│   ├── analytics.py       # Analytics & exports (6 endpoints)
│   └── notifications.py   # Notifications (3 endpoints)
└── models/                # Data models (future expansion)
```

## 🚀 Quick Start

### 1. Installation

```bash
cd /path/to/central-server/backend_v5

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your database credentials and settings
```

### 2. Configure Environment

Edit `.env` file:

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

### 3. Run the Server

```bash
# Development
python backend.py

# Production (with Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 backend:app
```

### 4. Verify Installation

```bash
curl http://localhost:5000/
curl http://localhost:5000/health
```

## 📊 Complete API Endpoints (78 Total)

### Health & Root (2 endpoints)
- `GET /` - API information and status
- `GET /health` - Health check

### Admin Operations (14 endpoints)
- `POST /api/admin/clients/create` - Create new client
- `DELETE /api/admin/clients/<id>` - Delete client
- `POST /api/admin/clients/<id>/regenerate-token` - Regenerate token
- `GET /api/admin/clients/<id>/token` - Get client token
- `GET /api/admin/stats` - Global statistics
- `GET /api/admin/clients` - List all clients
- `GET /api/admin/clients/growth` - Client growth data
- `GET /api/admin/instances` - All instances (global)
- `GET /api/admin/agents` - All agents (global)
- `GET /api/admin/activity` - System activity log
- `GET /api/admin/system-health` - System health metrics
- `GET /api/admin/search` - Global search
- `GET /api/admin/pools/statistics` - Pool statistics
- `GET /api/admin/agents/health-summary` - Agent health summary

### Client Management (3 endpoints)
- `GET /api/client/validate` - Validate client token
- `GET /api/client/<id>` - Get client details
- `GET /api/client/<id>/agents` - Get client's agents

### Agent Operations (12 endpoints)
- `POST /api/agents/register` - Register new agent
- `POST /api/agents/<id>/heartbeat` - Agent heartbeat
- `GET /api/agents/<id>/config` - Get agent configuration
- `GET /api/agents/<id>/instances-to-terminate` - Get termination list
- `POST /api/agents/<id>/termination-report` - Report termination
- `POST /api/agents/<id>/rebalance-recommendation` - Handle rebalance
- `GET /api/agents/<id>/replica-config` - Get replica config
- `POST /api/agents/<id>/decide` - Get switching decision
- `GET /api/agents/<id>/switch-recommendation` - Get recommendation
- `POST /api/agents/<id>/issue-switch-command` - Issue switch command
- `GET /api/agents/<id>/statistics` - Agent statistics
- `GET /api/agents/<id>/emergency-status` - Emergency status

### Instance Management (9 endpoints)
- `GET /api/client/<client_id>/instances` - List instances
- `GET /api/client/instances/<id>/pricing` - Get pricing
- `GET /api/client/instances/<id>/metrics` - Get metrics
- `GET /api/client/instances/<id>/price-history` - Price history
- `GET /api/client/instances/<id>/available-options` - Available pools
- `POST /api/client/instances/<id>/force-switch` - Force switch
- `GET /api/client/instances/<id>/logs` - Instance logs
- `GET /api/client/instances/<id>/pool-volatility` - Pool volatility
- `POST /api/client/instances/<id>/simulate-switch` - Simulate switch

### Replica Operations (1 endpoint)
- `GET /api/client/<id>/replicas` - List replicas

### Decision Engine & ML (5 endpoints)
- `POST /api/admin/decision-engine/upload` - Upload engine
- `POST /api/admin/ml-models/upload` - Upload ML models
- `POST /api/admin/ml-models/activate` - Activate models
- `POST /api/admin/ml-models/fallback` - Fallback to previous
- `GET /api/admin/ml-models/sessions` - List model sessions

### Commands (2 endpoints)
- `GET /api/agents/<id>/pending-commands` - Get pending commands
- `POST /api/agents/<id>/commands/<id>/executed` - Report execution

### Reporting & Telemetry (4 endpoints)
- `POST /api/agents/<id>/pricing-report` - Report pricing data
- `POST /api/agents/<id>/switch-report` - Report switch event
- `POST /api/agents/<id>/termination` - Report termination
- `POST /api/agents/<id>/cleanup-report` - Report cleanup

### Analytics & Exports (6 endpoints)
- `GET /api/client/<id>/savings` - Savings data
- `GET /api/client/<id>/switch-history` - Switch history
- `GET /api/client/<id>/export/savings` - Export savings CSV
- `GET /api/client/<id>/export/switch-history` - Export history CSV
- `GET /api/admin/export/global-stats` - Export global stats
- `GET /api/client/<id>/stats/charts` - Chart data

### Notifications (3 endpoints)
- `GET /api/notifications` - Get notifications
- `POST /api/notifications/<id>/mark-read` - Mark as read
- `POST /api/notifications/mark-all-read` - Mark all as read

### Advanced Features (3 endpoints)
- `GET /api/client/<id>/analytics/downtime` - Downtime analytics
- `POST /api/admin/bulk/execute` - Bulk operations
- `POST /api/client/<id>/pricing-alerts` - Pricing alerts

### Real-Time (1 endpoint)
- `GET /api/events/stream` - Server-Sent Events stream

## 🏗️ Architecture Overview

### Modular Design Benefits

**Before (Monolithic):**
- Single file: 8,930 lines
- Hard to navigate and maintain
- Mixed concerns in one file

**After (Modular):**
- 20 organized files
- Clear separation of concerns
- Easy to find and modify code
- Better testability

### Module Responsibilities

**config/** - Configuration Management
- Environment variables
- Application settings
- Path management
- Feature flags

**core/** - Core Infrastructure
- `database.py` - Connection pooling, query execution
- `auth.py` - Authentication decorators for admin and clients
- `utils.py` - Validation, formatting, error responses

**routes/** - API Endpoints
- Each file handles a specific domain (agents, instances, etc.)
- Uses Flask Blueprints for modularity
- Complete isolation between modules

## 🔐 Security Features

### Authentication
- **Admin endpoints**: Require `Authorization: Bearer <admin_token>`
- **Client endpoints**: Require `Authorization: Bearer <client_token>`
- **Token validation**: Database lookup for client tokens

### Security Best Practices
- SQL injection protection (parameterized queries)
- Input validation on all endpoints
- CORS configuration
- Password/token hashing (where applicable)
- Secure token generation (cryptographically random)

## 📝 Database Schema

**Required MySQL version**: 8.0+

**Main Tables:**
- `clients` - Client accounts
- `agents` - Monitoring agents
- `instances` - EC2 instances
- `switches` - Switch events history
- `replicas` - Replica instances
- `commands` - Command queue
- `notifications` - User notifications
- `spot_pricing_history` - Pricing data
- `system_events` - System event log

## 🧪 Testing

### Test Health Endpoint
```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "status": "healthy",
    "timestamp": "2024-11-26T10:00:00",
    "database": "connected"
  }
}
```

### Test Admin Endpoint
```bash
curl -H "Authorization: Bearer your-admin-token" \
  http://localhost:5000/api/admin/stats
```

### Test Client Endpoint
```bash
curl -H "Authorization: Bearer client-token" \
  http://localhost:5000/api/client/client-id
```

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
- Check `DB_HOST` and `DB_PORT`

**Authentication Failures:**
- Verify token in Authorization header
- Check token format: `Bearer <token>`
- Confirm client/admin token matches `.env`

**Module Import Errors:**
- Ensure all `__init__.py` files exist
- Check Python path: `sys.path` includes backend_v5
- Verify dependencies: `pip install -r requirements.txt`

## 🚀 Deployment

### Production Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_DEBUG=False`
- [ ] Use strong `ADMIN_TOKEN`
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Use HTTPS (reverse proxy with nginx)
- [ ] Set up monitoring (health check endpoint)
- [ ] Configure gunicorn workers appropriately

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
Description=AWS Spot Optimizer Backend v5
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

## 📈 Performance

### Connection Pooling
- Default pool size: 10 connections
- Automatic reconnection on failure
- Connection recycling after use

### Optimization Tips
- Increase `DB_POOL_SIZE` for high traffic
- Use caching for frequently accessed data
- Enable query result caching where appropriate
- Monitor slow queries and add indexes

## 🔄 Migration from Old Backend

If migrating from the monolithic `backend.py`:

1. **Database Schema**: No changes required (100% compatible)
2. **Environment Variables**: Same variables, copy from old `.env`
3. **API Endpoints**: All endpoints preserved with same paths
4. **Agents**: No changes required, agents work without modification
5. **Frontend**: No changes required, API contract maintained

### Side-by-Side Testing
```bash
# Run old backend on port 5000
python backend/backend.py

# Run new backend on port 5001
FLASK_PORT=5001 python backend_v5/backend.py
```

## 📚 API Documentation

For complete API documentation with request/response examples, see:
- Frontend integration: Check `apiClient.jsx` in frontend
- Postman collection: Available in `/docs` folder
- OpenAPI spec: Coming soon

## 🤝 Contributing

### Adding a New Endpoint

1. **Choose the appropriate route module** (or create new one)
2. **Add the endpoint**:
```python
@module_bp.route('/new-endpoint', methods=['POST'])
@require_client_auth
def new_endpoint(authenticated_client_id=None):
    try:
        # Implementation
        return jsonify(success_response(data))
    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify(*error_response("Error message", "ERROR_CODE", 500))
```
3. **Test the endpoint**
4. **Update this README**

### Code Style
- Use docstrings for all functions
- Follow PEP 8 style guide
- Add logging for important operations
- Use type hints where helpful
- Handle errors with try/except blocks

## 📞 Support

For issues, questions, or contributions:
- Check logs first: `logs/error.log`
- Review this README
- Check database connectivity
- Verify environment configuration

## 📄 License

Proprietary - AWS Spot Optimizer Team

---

**Version**: 5.0
**Last Updated**: 2024-11-26
**Maintained By**: AWS Spot Optimizer Team
