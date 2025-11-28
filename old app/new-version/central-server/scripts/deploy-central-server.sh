#!/bin/bash

# ============================================================================
# AWS SPOT OPTIMIZER - CENTRAL SERVER DEPLOYMENT SCRIPT
# ============================================================================
# Version: 7.0
# Description: Production-ready deployment script with comprehensive setup
# Requirements: Ubuntu 20.04+ or Amazon Linux 2023+
# ============================================================================

set -e  # Exit on error

# ============================================================================
# COLOR CODES FOR OUTPUT
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================
log "Starting AWS Spot Optimizer Central Server Deployment..."
log "=" ================================================================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Do not run this script as root. Run as a regular user with sudo privileges."
    exit 1
fi

# Check sudo privileges
if ! sudo -n true 2>/dev/null; then
    error "User $USER does not have sudo privileges"
    exit 1
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
    log "Detected OS: $OS $VER"
else
    error "Cannot detect OS. /etc/os-release not found."
    exit 1
fi

# Check internet connectivity
if ! ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    error "No internet connectivity. Please check your network."
    exit 1
fi

# Check disk space (need at least 10GB)
AVAILABLE_SPACE=$(df / | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_SPACE" -lt 10485760 ]; then  # 10GB in KB
    error "Insufficient disk space. Need at least 10GB available."
    exit 1
fi

log "Pre-flight checks passed"

# ============================================================================
# GET PUBLIC IP (Using IMDSv2)
# ============================================================================
log "Detecting public IP address..."

# Try IMDSv2 first (required for newer EC2 instances)
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" \
    --connect-timeout 5 2>/dev/null || echo "")

if [ -n "$TOKEN" ]; then
    # IMDSv2 success
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/meta-data/public-ipv4 \
        --connect-timeout 5 2>/dev/null || echo "")
    INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/meta-data/instance-id \
        --connect-timeout 5 2>/dev/null || echo "")
    REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
        http://169.254.169.254/latest/meta-data/placement/region \
        --connect-timeout 5 2>/dev/null || echo "")
fi

# Fallback to IMDSv1 if IMDSv2 failed
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 \
        --connect-timeout 5 2>/dev/null || echo "")
    INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id \
        --connect-timeout 5 2>/dev/null || echo "")
    REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region \
        --connect-timeout 5 2>/dev/null || echo "")
fi

# Fallback to external service if not on EC2
if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "127.0.0.1")
    INSTANCE_ID="local"
    REGION="local"
    warn "Not running on EC2. Using external IP detection."
fi

log "Public IP: $PUBLIC_IP"
log "Instance ID: $INSTANCE_ID"
log "Region: $REGION"

# ============================================================================
# USER INPUTS
# ============================================================================
info "=" ================================================================================"
info "CONFIGURATION"
info "============================================================================="

read -p "Enter MySQL root password [auto-generate if empty]: " MYSQL_ROOT_PASSWORD
if [ -z "$MYSQL_ROOT_PASSWORD" ]; then
    MYSQL_ROOT_PASSWORD=$(openssl rand -base64 24)
    log "Generated MySQL root password: $MYSQL_ROOT_PASSWORD"
fi

read -p "Enter database name [default: spot_optimizer]: " DB_NAME
DB_NAME=${DB_NAME:-spot_optimizer}

read -p "Enter database user [default: spot_user]: " DB_USER
DB_USER=${DB_USER:-spot_user}

read -p "Enter database password [auto-generate if empty]: " DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    DB_PASSWORD=$(openssl rand -base64 24)
    log "Generated database password: $DB_PASSWORD"
fi

read -p "Enter backend port [default: 5000]: " BACKEND_PORT
BACKEND_PORT=${BACKEND_PORT:-5000}

read -p "Enter frontend port [default: 3000]: " FRONTEND_PORT
FRONTEND_PORT=${FRONTEND_PORT:-3000}

# ============================================================================
# DIRECTORY STRUCTURE SETUP
# ============================================================================
log "Creating directory structure..."

# Create all directories with proper ownership from start
sudo mkdir -p /opt/spot-optimizer/{backend,frontend}
sudo mkdir -p /var/lib/spot-optimizer/{data,backups}
sudo mkdir -p /var/log/spot-optimizer
sudo mkdir -p /etc/spot-optimizer

# Set ownership
sudo chown -R $USER:$USER /opt/spot-optimizer
sudo chown -R $USER:$USER /var/lib/spot-optimizer
sudo chown -R $USER:$USER /var/log/spot-optimizer
sudo chown root:root /etc/spot-optimizer

# Set permissions
chmod 755 /opt/spot-optimizer
chmod 755 /var/lib/spot-optimizer
chmod 755 /var/log/spot-optimizer
chmod 750 /etc/spot-optimizer

log "Directory structure created"

# ============================================================================
# INSTALL DEPENDENCIES
# ============================================================================
log "Installing system dependencies..."

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    # Ubuntu/Debian
    sudo apt-get update -y -qq
    DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq \
        curl \
        git \
        wget \
        unzip \
        build-essential \
        python3 \
        python3-pip \
        python3-venv \
        mysql-client \
        nginx \
        jq \
        ca-certificates \
        gnupg \
        lsb-release \
        > /dev/null 2>&1

elif [ "$OS" = "amzn" ] || [ "$OS" = "rhel" ] || [ "$OS" = "centos" ]; then
    # Amazon Linux / RHEL / CentOS
    sudo yum update -y -q
    sudo yum install -y -q \
        curl \
        git \
        wget \
        unzip \
        gcc \
        make \
        python3 \
        python3-pip \
        python3-devel \
        mysql \
        nginx \
        jq \
        ca-certificates \
        > /dev/null 2>&1
else
    error "Unsupported OS: $OS"
    exit 1
fi

log "System dependencies installed"

# ============================================================================
# INSTALL DOCKER
# ============================================================================
log "Installing Docker..."

# Check if Docker already installed
if command -v docker &> /dev/null; then
    log "Docker already installed: $(docker --version)"
else
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        # Remove old versions
        sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

        # Add Docker's official GPG key
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

        # Set up repository
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
          $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Install Docker
        sudo apt-get update -y -qq
        sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null 2>&1

    elif [ "$OS" = "amzn" ]; then
        # Amazon Linux
        sudo yum install -y -q docker
        sudo systemctl start docker
        sudo systemctl enable docker
    fi

    # Add user to docker group
    sudo usermod -aG docker $USER
    log "Docker installed. Note: Group membership requires logout/login OR use 'sg docker -c' for immediate effect"
fi

# Start Docker if not running
if ! sudo systemctl is-active --quiet docker; then
    sudo systemctl start docker
    sudo systemctl enable docker
fi

log "Docker is running"

# ============================================================================
# CREATE DOCKER NETWORK
# ============================================================================
log "Creating Docker network..."

if ! docker network inspect spot-network > /dev/null 2>&1; then
    docker network create spot-network
    log "Docker network 'spot-network' created"
else
    log "Docker network 'spot-network' already exists"
fi

# ============================================================================
# SETUP MYSQL WITH DOCKER VOLUME
# ============================================================================
log "Setting up MySQL database..."

# Create Docker volume for MySQL data (better than bind mount)
if ! docker volume inspect spot-mysql-data > /dev/null 2>&1; then
    docker volume create spot-mysql-data
    log "Docker volume 'spot-mysql-data' created"
else
    log "Docker volume 'spot-mysql-data' already exists"
fi

# Stop and remove existing MySQL container if exists
docker stop spot-mysql 2>/dev/null || true
docker rm spot-mysql 2>/dev/null || true

# Run MySQL container
log "Starting MySQL container..."
docker run -d \
    --name spot-mysql \
    --network spot-network \
    -p 3306:3306 \
    -e MYSQL_ROOT_PASSWORD="$MYSQL_ROOT_PASSWORD" \
    -e MYSQL_DATABASE="$DB_NAME" \
    -v spot-mysql-data:/var/lib/mysql \
    --restart unless-stopped \
    mysql:8.0

# Wait for MySQL to be ready
log "Waiting for MySQL to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker exec spot-mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        if docker exec spot-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "SELECT 1;" > /dev/null 2>&1; then
            log "MySQL is ready"
            break
        fi
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        error "MySQL failed to start after $MAX_ATTEMPTS attempts"
        exit 1
    fi
    sleep 2
done

# Create database user (MySQL 8.0 requires CREATE USER before GRANT)
log "Creating database user..."
docker exec spot-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<EOF
CREATE USER IF NOT EXISTS '$DB_USER'@'%' IDENTIFIED BY '$DB_PASSWORD';
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
CREATE USER IF NOT EXISTS '$DB_USER'@'172.18.%' IDENTIFIED BY '$DB_PASSWORD';

GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'%';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'172.18.%';

FLUSH PRIVILEGES;
EOF

log "Database user created with grants for %, localhost, and Docker network"

# ============================================================================
# CLONE REPOSITORY
# ============================================================================
log "Cloning repository..."

cd /opt/spot-optimizer

if [ ! -d "ml-final-v3" ]; then
    git clone https://github.com/atharva0608/ml-final-v3.git
    log "Repository cloned"
else
    log "Repository already exists, pulling latest changes..."
    cd ml-final-v3
    git pull
    cd ..
fi

# Copy backend and frontend to deployment directories
log "Copying application files..."
cp -r ml-final-v3/new-version/central-server/* /opt/spot-optimizer/backend/
cp -r ml-final-v3/new-version/central-server/frontend/* /opt/spot-optimizer/frontend/

# ============================================================================
# IMPORT DATABASE SCHEMA
# ============================================================================
log "Importing database schema..."

# Use optimized schema if available, fall back to regular schema
if [ -f "/opt/spot-optimizer/backend/database/schema_optimized.sql" ]; then
    SCHEMA_FILE="/opt/spot-optimizer/backend/database/schema_optimized.sql"
    log "Using optimized schema v7.0"
else
    SCHEMA_FILE="/opt/spot-optimizer/backend/database/schema.sql"
    log "Using standard schema v6.0"
fi

docker exec -i spot-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" "$DB_NAME" < "$SCHEMA_FILE"

# Verify schema import
TABLE_COUNT=$(docker exec spot-mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" -D "$DB_NAME" -se "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME';")
log "Schema imported successfully. Tables created: $TABLE_COUNT"

# ============================================================================
# SETUP BACKEND (Python Flask)
# ============================================================================
log "Setting up backend..."

cd /opt/spot-optimizer/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel --quiet

# Install dependencies
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    log "Backend dependencies installed"
else
    # Install minimal Flask setup if requirements.txt missing
    pip install flask flask-cors mysql-connector-python boto3 --quiet
    log "Minimal backend dependencies installed"
fi

# Create .env file
cat > /opt/spot-optimizer/backend/.env <<EOF
# Database Configuration
DB_HOST=spot-mysql
DB_PORT=3306
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=$BACKEND_PORT

# CORS
CORS_ORIGINS=*

# Logging
LOG_LEVEL=INFO
LOG_DIR=/var/log/spot-optimizer
EOF

chmod 600 /opt/spot-optimizer/backend/.env

log "Backend configured"

# ============================================================================
# SETUP FRONTEND (React)
# ============================================================================
log "Setting up frontend..."

cd /opt/spot-optimizer/frontend

# Install Node.js LTS (v20.x) if not already installed
if ! command -v node &> /dev/null || [ "$(node -v | cut -d'.' -f1 | tr -d 'v')" -lt 18 ]; then
    log "Installing Node.js LTS..."

    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y -qq nodejs > /dev/null 2>&1
    elif [ "$OS" = "amzn" ]; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
        sudo yum install -y -q nodejs
    fi

    log "Node.js installed: $(node -v)"
else
    log "Node.js already installed: $(node -v)"
fi

# Update API URL in frontend config
log "Configuring frontend API URL..."
find . -type f \( -name '*.jsx' -o -name '*.js' \) -exec sed -i "s|http://localhost:5000|http://$PUBLIC_IP:$BACKEND_PORT|g" {} \;
log "API URL updated to http://$PUBLIC_IP:$BACKEND_PORT"

# Install dependencies and build
log "Building frontend (this may take a few minutes)..."
npm install --legacy-peer-deps --silent > /dev/null 2>&1
npm run build > /dev/null 2>&1

# Copy build to nginx root
sudo mkdir -p /var/www/spot-optimizer
sudo cp -r dist/* /var/www/spot-optimizer/
sudo chown -R www-data:www-data /var/www/spot-optimizer

log "Frontend built and deployed"

# ============================================================================
# CONFIGURE NGINX
# ============================================================================
log "Configuring Nginx..."

sudo tee /etc/nginx/sites-available/spot-optimizer > /dev/null <<EOF
server {
    listen $FRONTEND_PORT;
    server_name $PUBLIC_IP;

    # Frontend root
    root /var/www/spot-optimizer;
    index index.html;

    # Large headers for JWT tokens
    large_client_header_buffers 4 32k;

    # Frontend SPA routing
    location / {
        try_files \$uri \$uri/ /index.html;

        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Accept,Authorization,Cache-Control,Content-Type,DNT,If-Modified-Since,Keep-Alive,Origin,User-Agent,X-Requested-With' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_http_version 1.1;

        # Forward headers
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffers
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;

        # CORS headers (for API)
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Accept,Authorization,Cache-Control,Content-Type,DNT,If-Modified-Since,Keep-Alive,Origin,User-Agent,X-Requested-With' always;
        add_header 'Access-Control-Expose-Headers' 'Content-Length,Content-Range' always;

        # Handle OPTIONS for CORS preflight
        if (\$request_method = 'OPTIONS') {
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain charset=UTF-8';
            add_header 'Content-Length' 0;
            return 204;
        }
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Test Nginx configuration
if ! sudo nginx -t; then
    error "Nginx configuration test failed"
    exit 1
fi

# Enable site
sudo ln -sf /etc/nginx/sites-available/spot-optimizer /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Restart Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx

log "Nginx configured and running"

# ============================================================================
# CREATE SYSTEMD SERVICE FOR BACKEND
# ============================================================================
log "Creating systemd service for backend..."

sudo tee /etc/systemd/system/spot-optimizer-backend.service > /dev/null <<EOF
[Unit]
Description=AWS Spot Optimizer Backend API
After=network-online.target docker.service spot-mysql
Wants=network-online.target docker.service
Documentation=https://github.com/atharva0608/ml-final-v3

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=/opt/spot-optimizer/backend

# Environment
EnvironmentFile=/opt/spot-optimizer/backend/.env

# Start command
ExecStart=/opt/spot-optimizer/backend/venv/bin/python3 backend.py

# Restart policy
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/spot-optimizer/backend.log
StandardError=append:/var/log/spot-optimizer/backend-error.log
SyslogIdentifier=spot-optimizer-backend

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable spot-optimizer-backend
sudo systemctl start spot-optimizer-backend

log "Backend service created and started"

# ============================================================================
# SAVE CONFIGURATION
# ============================================================================
log "Saving configuration..."

sudo tee /etc/spot-optimizer/server-config.env > /dev/null <<EOF
# AWS Spot Optimizer Central Server Configuration
# Generated on: $(date)

# Server Details
PUBLIC_IP=$PUBLIC_IP
INSTANCE_ID=$INSTANCE_ID
REGION=$REGION

# Database
DB_HOST=spot-mysql
DB_PORT=3306
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# MySQL Root
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD

# Ports
BACKEND_PORT=$BACKEND_PORT
FRONTEND_PORT=$FRONTEND_PORT

# Deployment
DEPLOYED_AT=$(date -Iseconds)
DEPLOYED_BY=$USER
EOF

sudo chmod 600 /etc/spot-optimizer/server-config.env

# ============================================================================
# CREATE HELPER SCRIPTS
# ============================================================================
log "Creating helper scripts..."

# Status script
cat > /opt/spot-optimizer/status.sh <<'SCRIPT_END'
#!/bin/bash
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================================================="
echo "AWS Spot Optimizer - System Status"
echo "============================================================================="

# Backend service
if systemctl is-active --quiet spot-optimizer-backend; then
    echo -e "Backend Service:  ${GREEN}RUNNING${NC}"
else
    echo -e "Backend Service:  ${RED}STOPPED${NC}"
fi

# MySQL container
if docker ps | grep -q spot-mysql; then
    echo -e "MySQL Container:  ${GREEN}RUNNING${NC}"
else
    echo -e "MySQL Container:  ${RED}STOPPED${NC}"
fi

# Nginx
if systemctl is-active --quiet nginx; then
    echo -e "Nginx:            ${GREEN}RUNNING${NC}"
else
    echo -e "Nginx:            ${RED}STOPPED${NC}"
fi

# API Health Check
API_URL="http://localhost:$(grep BACKEND_PORT /opt/spot-optimizer/backend/.env | cut -d'=' -f2)/api/health"
if curl -s "$API_URL" | grep -q "ok"; then
    echo -e "API Health:       ${GREEN}OK${NC}"
else
    echo -e "API Health:       ${RED}FAILED${NC}"
fi

echo "============================================================================="
echo "Recent Backend Logs (last 10 lines):"
echo "============================================================================="
tail -10 /var/log/spot-optimizer/backend.log

echo ""
echo "For full logs, run: sudo journalctl -u spot-optimizer-backend -f"
SCRIPT_END

chmod +x /opt/spot-optimizer/status.sh

# Logs script
cat > /opt/spot-optimizer/logs.sh <<'SCRIPT_END'
#!/bin/bash
echo "Select log source:"
echo "1) Backend (systemd journal)"
echo "2) Backend (application log)"
echo "3) Backend (error log)"
echo "4) MySQL container"
echo "5) Nginx access"
echo "6) Nginx error"
read -p "Enter choice [1-6]: " choice

case $choice in
    1) sudo journalctl -u spot-optimizer-backend -f ;;
    2) tail -f /var/log/spot-optimizer/backend.log ;;
    3) tail -f /var/log/spot-optimizer/backend-error.log ;;
    4) docker logs -f spot-mysql ;;
    5) sudo tail -f /var/log/nginx/access.log ;;
    6) sudo tail -f /var/log/nginx/error.log ;;
    *) echo "Invalid choice" ;;
esac
SCRIPT_END

chmod +x /opt/spot-optimizer/logs.sh

# Restart script
cat > /opt/spot-optimizer/restart.sh <<'SCRIPT_END'
#!/bin/bash
GREEN='\033[0;32m'
NC='\033[0m'

echo "Restarting AWS Spot Optimizer services..."

# Restart MySQL
echo -n "Restarting MySQL... "
docker restart spot-mysql
sleep 5
echo -e "${GREEN}DONE${NC}"

# Restart backend
echo -n "Restarting backend... "
sudo systemctl restart spot-optimizer-backend
sleep 2
echo -e "${GREEN}DONE${NC}"

# Restart Nginx
echo -n "Restarting Nginx... "
sudo systemctl restart nginx
echo -e "${GREEN}DONE${NC}"

echo ""
echo "All services restarted. Run ./status.sh to verify."
SCRIPT_END

chmod +x /opt/spot-optimizer/restart.sh

log "Helper scripts created: status.sh, logs.sh, restart.sh"

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================
clear

cat > /home/$USER/CENTRAL_SERVER_SETUP_COMPLETE.txt <<EOF
============================================================================
AWS SPOT OPTIMIZER - CENTRAL SERVER DEPLOYMENT COMPLETE
============================================================================

Deployed on: $(date)
Public IP: $PUBLIC_IP
Instance ID: $INSTANCE_ID
Region: $REGION

============================================================================
ACCESS URLS
============================================================================

Dashboard:  http://$PUBLIC_IP:$FRONTEND_PORT
API:        http://$PUBLIC_IP:$BACKEND_PORT/api
Health:     http://$PUBLIC_IP:$BACKEND_PORT/api/health

============================================================================
CREDENTIALS
============================================================================

MySQL Root Password: $MYSQL_ROOT_PASSWORD
Database Name:       $DB_NAME
Database User:       $DB_USER
Database Password:   $DB_PASSWORD

⚠️  IMPORTANT: Save these credentials securely!

============================================================================
HELPER SCRIPTS
============================================================================

Status:     /opt/spot-optimizer/status.sh
Logs:       /opt/spot-optimizer/logs.sh
Restart:    /opt/spot-optimizer/restart.sh

============================================================================
DIRECTORY STRUCTURE
============================================================================

Application:  /opt/spot-optimizer/
Data:         /var/lib/spot-optimizer/
Logs:         /var/log/spot-optimizer/
Config:       /etc/spot-optimizer/

============================================================================
NEXT STEPS
============================================================================

1. Verify installation:
   /opt/spot-optimizer/status.sh

2. Access dashboard:
   http://$PUBLIC_IP:$FRONTEND_PORT

3. Register first agent:
   - Get client token from dashboard
   - Run agent installation script on EC2 instances

4. Configure security groups:
   - Allow inbound on port $FRONTEND_PORT (HTTP)
   - Allow inbound on port $BACKEND_PORT (API)
   - Allow inbound on port 3306 (MySQL) from agent IPs only

5. Setup monitoring:
   - Check logs regularly: /opt/spot-optimizer/logs.sh
   - Monitor disk space: df -h
   - Monitor MySQL: docker exec spot-mysql mysql -u root -p

============================================================================
TROUBLESHOOTING
============================================================================

Service not starting:
  sudo journalctl -u spot-optimizer-backend -n 100

Database connection issues:
  docker exec spot-mysql mysql -u $DB_USER -p$DB_PASSWORD -e "SELECT 1;"

API not responding:
  curl http://localhost:$BACKEND_PORT/api/health

Frontend not loading:
  sudo nginx -t
  sudo systemctl status nginx

============================================================================
SUPPORT
============================================================================

Documentation: https://github.com/atharva0608/ml-final-v3
Issues: https://github.com/atharva0608/ml-final-v3/issues

============================================================================
EOF

cat /home/$USER/CENTRAL_SERVER_SETUP_COMPLETE.txt

log "=" ================================================================================"
log "DEPLOYMENT COMPLETE!"
log "Setup summary saved to: /home/$USER/CENTRAL_SERVER_SETUP_COMPLETE.txt"
log "=" ================================================================================"
