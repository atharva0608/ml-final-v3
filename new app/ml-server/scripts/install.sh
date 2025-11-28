#!/bin/bash
# ML Server Installation Script
# Based on SESSION_MEMORY.md installation guide

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

log "Starting ML Server Installation..."

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please do not run as root. This script will use sudo when needed."
    exit 1
fi

# Update system
log "Step 1: Updating system packages..."
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install system dependencies
log "Step 2: Installing system dependencies..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    postgresql-15 \
    postgresql-contrib \
    redis-server \
    nginx \
    curl \
    wget \
    git \
    build-essential \
    libpq-dev \
    unzip

# Install Node.js 20.x LTS
log "Step 3: Installing Node.js 20.x LTS..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
fi
log "Node.js $(node --version) installed"

# Install AWS CLI v2
log "Step 4: Installing AWS CLI v2..."
if ! command -v aws &> /dev/null; then
    cd /tmp
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    sudo ./aws/install > /dev/null 2>&1
    rm -rf aws awscliv2.zip
fi
log "AWS CLI installed"

# Create directory structure
log "Step 5: Creating directory structure..."
APP_DIR="/opt/ml-server"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

mkdir -p $APP_DIR/backend
mkdir -p $APP_DIR/models/uploaded
mkdir -p $APP_DIR/decision_engine/uploaded
mkdir -p $APP_DIR/ml-frontend
mkdir -p $APP_DIR/scripts
mkdir -p /var/log/ml-server

log "Directory structure created"

# Setup Python virtual environment
log "Step 6: Setting up Python virtual environment..."
cd $APP_DIR/backend
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
log "Step 7: Installing Python dependencies..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

log "Python dependencies installed"
deactivate

# Setup PostgreSQL
log "Step 8: Configuring PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql << EOF
CREATE DATABASE ml_server;
CREATE USER ml_server WITH ENCRYPTED PASSWORD 'ml_server_password';
GRANT ALL PRIVILEGES ON DATABASE ml_server TO ml_server;
\c ml_server
GRANT ALL ON SCHEMA public TO ml_server;
EOF

log "PostgreSQL database created"

# Setup Redis
log "Step 9: Configuring Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

echo "maxmemory 2gb" | sudo tee -a /etc/redis/redis.conf > /dev/null
echo "maxmemory-policy allkeys-lru" | sudo tee -a /etc/redis/redis.conf > /dev/null
sudo systemctl restart redis-server

log "Redis configured"

# Create systemd service
log "Step 10: Creating systemd service..."
sudo tee /etc/systemd/system/ml-server-backend.service > /dev/null << SERVICE_EOF
[Unit]
Description=ML Server Backend (FastAPI)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/backend/.env
ExecStart=$APP_DIR/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl enable ml-server-backend

log "Systemd service created"

# Installation complete
log "============================================"
log "ML Server Installation Complete!"
log "============================================"
log "✓ Backend: FastAPI on port 8001"
log "✓ Frontend: React on port 3001"
log "✓ Database: PostgreSQL (ml_server)"
log "✓ Cache: Redis"
log ""
log "Next steps:"
log "  1. Copy application files to $APP_DIR/"
log "  2. Configure .env file"
log "  3. Run database migrations"
log "  4. Start services: $APP_DIR/scripts/start.sh"
log "============================================"
