#!/bin/bash
# ==============================================================================
# CloudOptim Core Platform - Complete Cleanup Script
# ==============================================================================
# This script removes ALL Core Platform components:
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
echo "  CLOUDOPTIM CORE PLATFORM - COMPLETE CLEANUP"
echo "======================================================================"
echo ""
warn "This script will REMOVE ALL components of the Core Platform:"
echo "  - Systemd service (core-platform)"
echo "  - Docker containers (core-postgres, core-redis)"
echo "  - Docker volumes (core-postgres-data, core-redis-data)"
echo "  - Docker network (core-network)"
echo "  - Application directory (/home/ubuntu/core-platform)"
echo "  - Log files (/home/ubuntu/core-platform-logs)"
echo "  - Helper scripts (/home/ubuntu/core-scripts)"
echo "  - Nginx configuration"
echo "  - Frontend files (/var/www/core-platform)"
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

if systemctl is-active --quiet core-platform; then
    sudo systemctl stop core-platform
    log "✓ Stopped core-platform service"
fi

if systemctl is-enabled --quiet core-platform 2>/dev/null; then
    sudo systemctl disable core-platform
    log "✓ Disabled core-platform service"
fi

if [ -f /etc/systemd/system/core-platform.service ]; then
    sudo rm /etc/systemd/system/core-platform.service
    log "✓ Removed service file"
fi

sudo systemctl daemon-reload
log "✓ Reloaded systemd"

# ==============================================================================
# STEP 2: REMOVE NGINX CONFIGURATION
# ==============================================================================

log "Step 2: Removing Nginx configuration..."

if [ -f /etc/nginx/sites-enabled/core-platform ]; then
    sudo rm /etc/nginx/sites-enabled/core-platform
    log "✓ Removed Nginx site (enabled)"
fi

if [ -f /etc/nginx/sites-available/core-platform ]; then
    sudo rm /etc/nginx/sites-available/core-platform
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

if docker ps -a | grep -q core-postgres; then
    docker stop core-postgres 2>/dev/null || true
    docker rm core-postgres 2>/dev/null || true
    log "✓ Removed core-postgres container"
fi

if docker ps -a | grep -q core-redis; then
    docker stop core-redis 2>/dev/null || true
    docker rm core-redis 2>/dev/null || true
    log "✓ Removed core-redis container"
fi

# ==============================================================================
# STEP 4: REMOVE DOCKER VOLUMES
# ==============================================================================

log "Step 4: Removing Docker volumes..."

if docker volume ls | grep -q core-postgres-data; then
    docker volume rm core-postgres-data 2>/dev/null || true
    log "✓ Removed core-postgres-data volume"
fi

if docker volume ls | grep -q core-redis-data; then
    docker volume rm core-redis-data 2>/dev/null || true
    log "✓ Removed core-redis-data volume"
fi

# ==============================================================================
# STEP 5: REMOVE DOCKER NETWORK
# ==============================================================================

log "Step 5: Removing Docker network..."

if docker network ls | grep -q core-network; then
    docker network rm core-network 2>/dev/null || true
    log "✓ Removed core-network"
fi

# ==============================================================================
# STEP 6: REMOVE APPLICATION DIRECTORIES
# ==============================================================================

log "Step 6: Removing application directories..."

if [ -d "/home/ubuntu/core-platform" ]; then
    sudo rm -rf /home/ubuntu/core-platform
    log "✓ Removed /home/ubuntu/core-platform"
fi

if [ -d "/home/ubuntu/core-platform-logs" ]; then
    sudo rm -rf /home/ubuntu/core-platform-logs
    log "✓ Removed /home/ubuntu/core-platform-logs"
fi

if [ -d "/home/ubuntu/core-scripts" ]; then
    sudo rm -rf /home/ubuntu/core-scripts
    log "✓ Removed /home/ubuntu/core-scripts"
fi

# ==============================================================================
# STEP 7: REMOVE FRONTEND FILES
# ==============================================================================

log "Step 7: Removing frontend files..."

if [ -d "/var/www/core-platform" ]; then
    sudo rm -rf /var/www/core-platform
    log "✓ Removed /var/www/core-platform"
fi

# ==============================================================================
# STEP 8: REMOVE SETUP SUMMARY
# ==============================================================================

log "Step 8: Removing setup files..."

if [ -f "/home/ubuntu/CORE_PLATFORM_SETUP_COMPLETE.txt" ]; then
    sudo rm /home/ubuntu/CORE_PLATFORM_SETUP_COMPLETE.txt
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
echo "  ✓ Docker containers (core-postgres, core-redis)"
echo "  ✓ Docker volumes"
echo "  ✓ Docker network"
echo "  ✓ Application directories"
echo "  ✓ Log files"
echo "  ✓ Helper scripts"
echo "  ✓ Nginx configuration"
echo "  ✓ Frontend files"
echo ""
log "Core Platform has been completely removed."
log "You can now run setup.sh again for a fresh installation."
echo ""
