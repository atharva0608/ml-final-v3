#!/bin/bash
# ==============================================================================
# CloudOptim ML Server - Complete Cleanup Script
# ==============================================================================
# This script removes ALL ML Server components:
# - Systemd services
# - Docker containers, volumes, networks
# - Application directories and files
# - Configuration files
# - Helper scripts
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# ==============================================================================
# CONFIRMATION
# ==============================================================================

echo ""
echo "======================================================================"
echo "  CLOUDOPTIM ML SERVER - COMPLETE CLEANUP"
echo "======================================================================"
echo ""
warn "This script will REMOVE ALL components of the ML Server:"
echo "  - Systemd service (ml-server)"
echo "  - Docker containers (ml-postgres, ml-redis)"
echo "  - Docker volumes (ml-postgres-data, ml-redis-data)"
echo "  - Docker network (ml-network)"
echo "  - Application directory (/home/ubuntu/ml-server)"
echo "  - Model files (/home/ubuntu/ml_models)"
echo "  - Engine files (/home/ubuntu/ml_engines)"
echo "  - Log files (/home/ubuntu/ml-server-logs)"
echo "  - Helper scripts (/home/ubuntu/ml-scripts)"
echo "  - Nginx configuration"
echo "  - Frontend files (/var/www/ml-server)"
echo ""
echo -e "${RED}WARNING: THIS CANNOT BE UNDONE!${NC}"
echo ""

read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

if [ "$confirmation" != "yes" ]; then
    log "Cleanup cancelled."
    exit 0
fi

echo ""
log "Starting cleanup process..."
echo ""

# ==============================================================================
# STEP 1: STOP AND REMOVE SYSTEMD SERVICE
# ==============================================================================

log "Step 1: Stopping and removing systemd service..."

if systemctl is-active --quiet ml-server; then
    sudo systemctl stop ml-server
    log "✓ Stopped ml-server service"
fi

if systemctl is-enabled --quiet ml-server 2>/dev/null; then
    sudo systemctl disable ml-server
    log "✓ Disabled ml-server service"
fi

if [ -f /etc/systemd/system/ml-server.service ]; then
    sudo rm /etc/systemd/system/ml-server.service
    log "✓ Removed service file"
fi

sudo systemctl daemon-reload
log "✓ Reloaded systemd"

# ==============================================================================
# STEP 2: REMOVE NGINX CONFIGURATION
# ==============================================================================

log "Step 2: Removing Nginx configuration..."

if [ -f /etc/nginx/sites-enabled/ml-server ]; then
    sudo rm /etc/nginx/sites-enabled/ml-server
    log "✓ Removed Nginx site (enabled)"
fi

if [ -f /etc/nginx/sites-available/ml-server ]; then
    sudo rm /etc/nginx/sites-available/ml-server
    log "✓ Removed Nginx site (available)"
fi

if systemctl is-active --quiet nginx; then
    sudo systemctl restart nginx 2>/dev/null || true
    log "✓ Restarted Nginx"
fi

# ==============================================================================
# STEP 3: STOP AND REMOVE DOCKER CONTAINERS
# ==============================================================================

log "Step 3: Stopping and removing Docker containers..."

if docker ps -a | grep -q ml-postgres; then
    docker stop ml-postgres 2>/dev/null || true
    docker rm ml-postgres 2>/dev/null || true
    log "✓ Removed ml-postgres container"
fi

if docker ps -a | grep -q ml-redis; then
    docker stop ml-redis 2>/dev/null || true
    docker rm ml-redis 2>/dev/null || true
    log "✓ Removed ml-redis container"
fi

# ==============================================================================
# STEP 4: REMOVE DOCKER VOLUMES
# ==============================================================================

log "Step 4: Removing Docker volumes..."

if docker volume ls | grep -q ml-postgres-data; then
    docker volume rm ml-postgres-data 2>/dev/null || true
    log "✓ Removed ml-postgres-data volume"
fi

if docker volume ls | grep -q ml-redis-data; then
    docker volume rm ml-redis-data 2>/dev/null || true
    log "✓ Removed ml-redis-data volume"
fi

# ==============================================================================
# STEP 5: REMOVE DOCKER NETWORK
# ==============================================================================

log "Step 5: Removing Docker network..."

if docker network ls | grep -q ml-network; then
    docker network rm ml-network 2>/dev/null || true
    log "✓ Removed ml-network"
fi

# ==============================================================================
# STEP 6: REMOVE APPLICATION DIRECTORIES
# ==============================================================================

log "Step 6: Removing application directories..."

if [ -d "/home/ubuntu/ml-server" ]; then
    sudo rm -rf /home/ubuntu/ml-server
    log "✓ Removed /home/ubuntu/ml-server"
fi

if [ -d "/home/ubuntu/ml_models" ]; then
    sudo rm -rf /home/ubuntu/ml_models
    log "✓ Removed /home/ubuntu/ml_models"
fi

if [ -d "/home/ubuntu/ml_engines" ]; then
    sudo rm -rf /home/ubuntu/ml_engines
    log "✓ Removed /home/ubuntu/ml_engines"
fi

if [ -d "/home/ubuntu/ml-server-logs" ]; then
    sudo rm -rf /home/ubuntu/ml-server-logs
    log "✓ Removed /home/ubuntu/ml-server-logs"
fi

if [ -d "/home/ubuntu/ml-scripts" ]; then
    sudo rm -rf /home/ubuntu/ml-scripts
    log "✓ Removed /home/ubuntu/ml-scripts"
fi

# ==============================================================================
# STEP 7: REMOVE FRONTEND FILES
# ==============================================================================

log "Step 7: Removing frontend files..."

if [ -d "/var/www/ml-server" ]; then
    sudo rm -rf /var/www/ml-server
    log "✓ Removed /var/www/ml-server"
fi

# ==============================================================================
# STEP 8: REMOVE SETUP SUMMARY
# ==============================================================================

log "Step 8: Removing setup files..."

if [ -f "/home/ubuntu/ML_SERVER_SETUP_COMPLETE.txt" ]; then
    sudo rm /home/ubuntu/ML_SERVER_SETUP_COMPLETE.txt
    log "✓ Removed setup summary"
fi

# ==============================================================================
# STEP 9: SUMMARY
# ==============================================================================

echo ""
log "======================================================================"
log "  CLEANUP COMPLETE"
log "======================================================================"
echo ""
info "Removed components:"
echo "  ✓ Systemd service"
echo "  ✓ Docker containers (ml-postgres, ml-redis)"
echo "  ✓ Docker volumes"
echo "  ✓ Docker network"
echo "  ✓ Application directories"
echo "  ✓ Model and engine files"
echo "  ✓ Log files"
echo "  ✓ Helper scripts"
echo "  ✓ Nginx configuration"
echo "  ✓ Frontend files"
echo ""
log "ML Server has been completely removed."
log "You can now run setup.sh again for a fresh installation."
echo ""
