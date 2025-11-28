# CloudOptim - New Architecture

**Version**: 2.0
**Created**: 2025-11-28
**Architecture**: Inference-Only ML Server + Core Platform

---

## 📋 Overview

This is the **new architecture** for CloudOptim with the following key changes:

1. **ML Server**: Inference-only (no training on server)
2. **Model Upload**: Upload pre-trained models via frontend
3. **Automatic Gap-Filling**: Solves "trained until October, need data until today" problem
4. **Core Platform**: Central backend, database, admin frontend
5. **Client Agent**: Lightweight Kubernetes agent

---

## 🗂️ Folder Structure

```
new app/
├── README.md                   # This file
├── memory.md                   # Architecture memory & documentation
├── ml-server/                  # ML inference & decision engine server
│   ├── SESSION_MEMORY.md      # ML server documentation
│   ├── models/                 # Model hosting (uploaded models)
│   ├── decision_engine/        # Pluggable decision engines
│   ├── data/                   # Gap filler & data fetchers
│   ├── api/                    # FastAPI server
│   └── ...
├── core-platform/              # Central backend, DB, admin UI
│   ├── SESSION_MEMORY.md      # Core platform documentation
│   ├── api/                    # Main REST API
│   ├── database/               # PostgreSQL schema & migrations
│   ├── admin-frontend/         # React admin dashboard
│   ├── services/               # Business logic
│   └── ...
├── client-agent/               # Lightweight Kubernetes agent
│   ├── SESSION_MEMORY.md      # Client agent documentation
│   ├── agent/                  # Agent implementation
│   ├── tasks/                  # Task executors
│   └── ...
├── common/                     # Shared components
│   ├── INTEGRATION_GUIDE.md   # Integration documentation
│   ├── schemas/                # Pydantic models
│   ├── auth/                   # Authentication
│   └── config/                 # Common configuration
└── infra/                      # Infrastructure as Code
    ├── docker-compose.yml      # Local development
    ├── kubernetes/             # K8s manifests
    └── terraform/              # Cloud infrastructure
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Node.js 18+ (for admin frontend)

### Local Development

#### 1. Start Infrastructure
```bash
cd infra/
docker-compose up -d postgres redis
```

#### 2. Start ML Server
```bash
cd ml-server/
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api/server.py
```
Server will run on: `http://localhost:8001`

#### 3. Start Core Platform
```bash
cd core-platform/

# Setup database
./scripts/setup_database.sh
./scripts/migrate_database.sh

# Start backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python api/main.py

# Start frontend (in separate terminal)
cd admin-frontend/
npm install
npm start
```
- API: `http://localhost:8000`
- Admin UI: `http://localhost:3000`

#### 4. Deploy Client Agent (on K8s cluster)
```bash
cd client-agent/
kubectl apply -f deployment.yaml
```

---

## 📖 Documentation

### Component Documentation
Each component has detailed `SESSION_MEMORY.md`:
- **[ml-server/SESSION_MEMORY.md](./ml-server/SESSION_MEMORY.md)** - ML server architecture
- **[core-platform/SESSION_MEMORY.md](./core-platform/SESSION_MEMORY.md)** - Central server design
- **[client-agent/SESSION_MEMORY.md](./client-agent/SESSION_MEMORY.md)** - Client agent implementation

### Architecture Documentation
- **[memory.md](./memory.md)** - Complete architecture overview
- **[common/INTEGRATION_GUIDE.md](./common/INTEGRATION_GUIDE.md)** - Integration patterns

---

## 🎯 Key Features

### 1. Inference-Only ML Server
- ❌ **No training** on this server
- ✅ Upload pre-trained models (`.pkl` files)
- ✅ Pluggable decision engines
- ✅ A/B testing of model versions

### 2. Automatic Gap-Filling
**Problem**: Model trained on data up to October, need predictions for today

**Solution**:
1. ML server detects gap (`trained_until` → `today`)
2. Pulls historic AWS price data automatically
3. Fills gap with feature engineering
4. Model ready for up-to-date predictions immediately

### 3. Model Upload via Frontend
- Drag-and-drop model upload UI
- Decision engine selection (dropdown)
- Gap-fill trigger & progress display
- Live charts (predictions vs actuals)

### 4. Live Decision Streaming
- Real-time predictions
- Actionable decisions (Spot optimization, bin packing, rightsizing)
- WebSocket streaming to dashboards

---

## 🔗 API Endpoints

### ML Server (Port 8001)
```
POST /api/v1/ml/models/upload       - Upload model
GET  /api/v1/ml/models/list         - List models
POST /api/v1/ml/models/activate     - Activate model version
POST /api/v1/ml/engines/upload      - Upload decision engine
POST /api/v1/ml/gap-filler/analyze  - Analyze data gaps
POST /api/v1/ml/gap-filler/fill     - Fill gaps
POST /api/v1/ml/predict/*           - Prediction endpoints
POST /api/v1/ml/decision/*          - Decision endpoints
```

### Core Platform (Port 8000)
```
GET  /api/v1/admin/clusters         - List clusters
GET  /api/v1/admin/savings          - Real-time savings
POST /api/v1/optimization/trigger   - Trigger optimization
GET  /api/v1/client/tasks           - Client agent tasks
POST /api/v1/client/metrics         - Submit metrics
```

---

## 🔄 Development Workflow

### Working on a Component

1. **Read the session memory**: `{component}/SESSION_MEMORY.md`
2. **Make changes** to the code
3. **Append updates** to session memory log section
4. **Update integration guide** if APIs change
5. **Test** the changes
6. **Commit** with descriptive message

### Example: Adding a New Feature to ML Server
```bash
cd ml-server/

# 1. Read documentation
cat SESSION_MEMORY.md

# 2. Make changes
vim api/routes/models.py

# 3. Update session memory
echo "
### 2025-11-28 - Added model validation feature
**Changes Made**:
- Implemented model validation on upload
- Added schema checking

**Files Modified**:
- api/routes/models.py
- models/validator.py
" >> SESSION_MEMORY.md

# 4. Test
pytest tests/

# 5. Commit
git add .
git commit -m "Add model validation on upload"
```

---

## 🧪 Testing

### Run Tests for All Components
```bash
# ML Server
cd ml-server && pytest tests/

# Core Platform
cd core-platform && pytest tests/

# Client Agent
cd client-agent && pytest tests/

# Integration tests
cd .. && pytest integration_tests/
```

---

## 🚢 Deployment

### Docker Compose (Development)
```bash
cd infra/
docker-compose up -d
```

### Kubernetes (Production)
```bash
cd infra/kubernetes/

# Deploy ML Server
kubectl apply -f ml-server/

# Deploy Core Platform
kubectl apply -f core-platform/

# Deploy Client Agent (per cluster)
kubectl apply -f client-agent/
```

---

## 📊 Architecture Diagrams

### High-Level Architecture
```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   ML Server      │     │ Core Platform    │     │  Client Agent    │
│  (Port 8001)     │◄───►│  (Port 8000)     │◄───►│ (Customer K8s)   │
│                  │     │                  │     │                  │
│ • Models         │     │ • REST API       │     │ • Task Executor  │
│ • Decisions      │     │ • PostgreSQL     │     │ • Metrics        │
│ • Gap Filler     │     │ • Admin UI       │     │ • Events         │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Data Flow: Model Upload & Gap-Fill
```
1. User uploads model via Admin UI
   Admin UI → Core Platform: POST /models/upload
   Core Platform → ML Server: POST /api/v1/ml/models/upload

2. ML Server stores model
   ML Server: Save to /models/uploaded/{model_id}.pkl
   ML Server: Extract metadata (trained_until date)

3. User triggers gap-fill
   Admin UI → ML Server: POST /api/v1/ml/gap-filler/fill

4. ML Server fills gap
   ML Server → AWS APIs: Get historic prices
   ML Server: Process & store data
   ML Server: Model ready for inference

5. User activates model
   Admin UI → ML Server: POST /api/v1/ml/models/activate
   ML Server: Set as active, start serving predictions
```

---

## 🐛 Troubleshooting

### ML Server not starting
- Check Python version (3.10+)
- Verify Redis connection
- Check MODEL_UPLOAD_DIR permissions

### Gap-filler failing
- Verify AWS credentials
- Check internet connectivity
- Verify instance types/regions in config

### Frontend build errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node version (18+)
- Verify API endpoint in .env

---

## 📝 Contributing

1. Read relevant `SESSION_MEMORY.md` file
2. Create feature branch
3. Make changes and update session memory
4. Write tests
5. Submit PR with descriptive message

---

## 🔗 Related Documentation

- **Root README**: [../../README.md](../../README.md)
- **Project Status**: [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md)
- **Old Architecture**: [../old app/](../old%20app/)

---

**Last Updated**: 2025-11-28
**Status**: Ready for implementation
