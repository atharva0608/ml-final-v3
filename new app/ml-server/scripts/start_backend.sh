#!/bin/bash
echo "Starting ML Server Backend..."
cd "$(dirname "$0")/../backend"
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
