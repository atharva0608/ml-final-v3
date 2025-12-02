# ML Server Scripts - Updated

## Changes Made to setup.sh

### 1. Backend Startup Script (start.sh)

**Location:** Line 442-459

Added PYTHONPATH export before starting uvicorn:

```bash
#!/bin/bash
cd /home/ubuntu/ml-server/backend
source venv/bin/activate

# Add ML server root to Python path for decision_engine imports
export PYTHONPATH="/home/ubuntu/ml-server:$PYTHONPATH"

if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

exec uvicorn main:app \
    --host 0.0.0.0 \
    --port 8001 \
    --workers 4 \
    --log-level info \
    --access-log \
    --use-colors
```

**Why:** The `decision_engine` module is located at `/home/ubuntu/ml-server/decision_engine/`, so we need to add `/home/ubuntu/ml-server` to Python's search path.

### 2. Systemd Service Configuration

**Location:** Line 566-568

Added PYTHONPATH environment variable:

```ini
Environment=PATH=$BACKEND_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/home/ubuntu/ml-server
```

**Why:** Systemd services need explicit environment variables. This ensures the backend can find `decision_engine` when started as a service.

## Summary of All Import Fixes

### Backend Code Changes
1. ✅ **decisions.py** - Added sys.path modification + mock fallbacks
2. ✅ **models.py** - Commented out unused database.schemas imports

### Deployment Script Changes  
3. ✅ **setup.sh** - Added PYTHONPATH to start.sh script
4. ✅ **setup.sh** - Added PYTHONPATH to systemd service

## How to Deploy

### On Production Server:

```bash
# Pull latest changes
cd ~/ml-final-v3
git pull origin local-atharva

# Re-run setup script
cd "new app/ml-server/scripts"
sudo bash setup.sh
```

The setup script will:
1. Update all files including the new backend routes
2. Create backend start.sh with PYTHONPATH
3. Create systemd service with PYTHONPATH
4. Start the backend - should now work without ModuleNotFoundError

### Manual Fix (if already deployed):

If you don't want to re-run the full setup:

```bash
# Update backend start script
cd /home/ubuntu/ml-server/backend
nano start.sh
```

Add this line after `source venv/bin/activate`:
```bash
export PYTHONPATH="/home/ubuntu/ml-server:$PYTHONPATH"
```

Then update systemd service:
```bash
sudo nano /etc/systemd/system/ml-server.service
```

Add under [Service] section:
```ini
Environment=PYTHONPATH=/home/ubuntu/ml-server
```

Then reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ml-server
sudo journalctl -u ml-server -f  # Check logs
```

## Verification

After deployment, check that backend starts successfully:

```bash
# 1. Check service status
sudo systemctl status ml-server

# 2. Check for errors in logs
sudo journalctl -u ml-server -n 100 --no-pager | grep -i error

# 3. Test API endpoint
curl http://localhost:8001/api/v1/ml/health
```

Should see:
- ✅ Service status: **active (running)**
- ✅ No ModuleNotFoundError in logs
- ✅ API responds with 200 OK

## Files Modified

- [setup.sh](file:///Users/atharvapudale/Desktop/backend-ecc/TESTINF/ml-final-v3/new%20app/ml-server/scripts/setup.sh) - Lines 442-459, 566-568
- [decisions.py](file:///Users/atharvapudale/Desktop/backend-ecc/TESTINF/ml-final-v3/new%20app/ml-server/backend/api/routes/decisions.py) - Lines 1-72
- [models.py](file:///Users/atharvapudale/Desktop/backend-ecc/TESTINF/ml-final-v3/new%20app/ml-server/backend/api/routes/models.py) - Lines 1-25
