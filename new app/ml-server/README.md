# ML Server - CloudOptim

**Machine Learning & Decision Engine Server for Agentless Kubernetes Cost Optimization**

## Overview

ML Server is a complete ML infrastructure component providing:
- **Inference-only ML model hosting** (pre-trained models, no production training)
- **8 CAST AI-compatible decision engines** for cost optimization
- **Data gap filling** for seamless model updates
- **Pricing data management** (Spot, On-Demand, Spot Advisor)
- **React dashboard** for model management and monitoring

## Architecture

**Agentless Design**:
- ❌ NO client-side agents or DaemonSets
- ✅ Remote Kubernetes API calls only
- ✅ AWS public data (Spot Advisor) for Day Zero operation
- ✅ Complete isolation from customer clusters

**Components**:
- **Backend**: FastAPI (Port 8001)
- **Frontend**: React Dashboard (Port 3001)
- **Database**: PostgreSQL (pricing data, models, decisions)
- **Cache**: Redis (Spot Advisor data, recent prices)

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 20.x LTS
- AWS CLI v2 (optional, for Spot Advisor data)

### Installation

```bash
# Automated installation (Ubuntu 22.04/24.04)
./scripts/install.sh

# Or manual installation
pip install -r requirements.txt
npm install --prefix ml-frontend
```

### Configuration

Edit `backend/.env`:
```bash
ML_SERVER_HOST=0.0.0.0
ML_SERVER_PORT=8001
DB_HOST=localhost
DB_NAME=ml_server
REDIS_HOST=localhost
```

### Start Services

```bash
# Backend
./scripts/start_backend.sh

# Frontend
./scripts/start_frontend.sh
```

### Access

- **Backend API**: http://localhost:8001/api/v1/ml/
- **API Docs**: http://localhost:8001/api/v1/ml/docs
- **Frontend Dashboard**: http://localhost:3001
- **Health Check**: http://localhost:8001/api/v1/ml/health

## Features

### 1. ML Model Management
- Upload pre-trained models (.pkl files)
- Version control and activation
- Hot-reload without downtime
- Performance metrics tracking

### 2. Decision Engines (8 CAST AI Features)
- **Spot Optimizer**: Select optimal Spot instances using AWS Spot Advisor
- **Bin Packing**: Consolidate workloads (Tetris algorithm)
- **Rightsizing**: Match instance sizes to workload requirements
- **Office Hours Scheduler**: Auto-scale dev/staging environments
- **Ghost Probe Scanner**: Detect zombie EC2 instances
- **Zombie Volume Cleanup**: Remove unattached EBS volumes
- **Network Optimizer**: Optimize cross-AZ traffic
- **OOMKilled Remediation**: Auto-fix OOMKilled pods

### 3. Data Gap Filling
- Automatic gap detection (trained_until_date → current_date)
- AWS pricing data fetcher
- Real-time progress tracking
- Background processing with status API

### 4. Model Refresh
- Manual or scheduled refresh (daily/weekly)
- Fetch latest pricing data from AWS APIs
- Hot-reload models with fresh data
- Refresh history tracking

### 5. Pricing Data Management
- Historical Spot prices (from AWS EC2 API)
- On-Demand pricing
- AWS Spot Advisor data (public interruption rates)
- PostgreSQL storage with indexed queries
- Redis caching for fast lookups

## API Endpoints

### Models
```http
POST /api/v1/ml/models/upload       # Upload model
GET  /api/v1/ml/models/list         # List models
POST /api/v1/ml/models/activate     # Activate version
GET  /api/v1/ml/models/{id}/details # Model details
```

### Decision Engines
```http
POST /api/v1/ml/engines/upload      # Upload engine
GET  /api/v1/ml/engines/list        # List engines
POST /api/v1/ml/decision/spot-optimize  # Spot optimization
POST /api/v1/ml/decision/bin-pack   # Bin packing
POST /api/v1/ml/decision/rightsize  # Rightsizing
# ... (8 decision endpoints total)
```

### Data Gap Filling
```http
POST /api/v1/ml/gap-filler/analyze  # Analyze gaps
POST /api/v1/ml/gap-filler/fill     # Fill gaps
GET  /api/v1/ml/gap-filler/status/{id}  # Progress
```

### Pricing Data
```http
GET  /api/v1/ml/pricing/spot        # Spot prices
GET  /api/v1/ml/pricing/on-demand   # On-Demand prices
GET  /api/v1/ml/pricing/spot-advisor  # Spot Advisor data
POST /api/v1/ml/pricing/fetch       # Manual fetch
```

See `docs/API_SPEC.md` and `SESSION_MEMORY.md` for complete API documentation.

## Database Schema

PostgreSQL tables:
- `ml_models` - Model metadata and versions
- `decision_engines` - Decision engine metadata
- `spot_prices` - Historical Spot pricing data
- `on_demand_prices` - On-Demand pricing data
- `spot_advisor_data` - AWS Spot Advisor interruption rates
- `data_gaps` - Gap analysis and fill tracking
- `model_refresh_history` - Refresh execution logs
- `predictions_log` - Prediction history
- `decision_execution_log` - Decision execution history

See `SESSION_MEMORY.md` lines 97-241 for complete schema.

## Development

### Run Tests
```bash
pytest tests/
```

### Database Migrations
```bash
cd backend
alembic upgrade head
```

### Fetch Spot Advisor Data
```bash
curl https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json | jq . > /tmp/spot-advisor-data.json
```

## Production Deployment

### Docker Compose
```bash
docker-compose up -d
```

### Systemd Service
```bash
sudo systemctl start ml-server-backend
sudo systemctl status ml-server-backend
```

### Environment Variables

See `config/ml_config.yaml` for all configuration options.

Key variables:
- `ML_SERVER_PORT`: Backend port (default: 8001)
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: PostgreSQL connection
- `REDIS_HOST`, `REDIS_PORT`: Redis connection
- `MODEL_UPLOAD_DIR`: Model storage directory
- `GAP_FILLER_ENABLED`: Enable automatic gap filling
- `ALLOW_MODEL_TRAINING`: Always `false` (inference-only)

## Day Zero Operation

ML Server works **immediately** without customer historical data:

1. **Spot Advisor Data**: Uses AWS public data (no customer data needed)
2. **Ghost Probe Scanner**: Cross-references EC2 vs K8s nodes instantly
3. **Rightsizing**: Deterministic lookup tables (no ML needed)
4. **Bin Packing**: Current cluster state analysis only

## Security

- All communication over HTTPS/TLS (production)
- No customer data stored (pricing data is public)
- Service account tokens encrypted at rest
- Least-privilege IAM roles
- API key authentication (TODO: implement)

## Documentation

- **SESSION_MEMORY.md**: Complete implementation guide (1972 lines)
- **docs/API_SPEC.md**: API endpoint reference
- **docs/DATABASE_SCHEMA.md**: Database schema details
- **docs/DECISION_ENGINES.md**: Decision engine algorithms
- **docs/FRONTEND_GUIDE.md**: Frontend usage guide

## Integration with Core Platform

ML Server is called by Core Platform for decision-making:

```
Core Platform → ML Server: POST /api/v1/ml/decision/spot-optimize
ML Server → Core Platform: DecisionResponse with recommendations
Core Platform → Customer Cluster: Execute recommendations via remote K8s API
```

ML Server **never** interacts with customer clusters directly (agentless).

## License

Proprietary - CloudOptim

## Support

For issues and questions, refer to SESSION_MEMORY.md or contact the development team.

---

**Last Updated**: 2025-11-28
**Version**: 1.0.0
**Architecture**: Agentless (No DaemonSets, remote API only)
