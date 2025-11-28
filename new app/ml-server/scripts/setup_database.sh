#!/bin/bash
echo "Setting up ML Server database..."
sudo -u postgres psql << SQL
CREATE DATABASE IF NOT EXISTS ml_server;
CREATE USER IF NOT EXISTS ml_server WITH ENCRYPTED PASSWORD 'ml_server_password';
GRANT ALL PRIVILEGES ON DATABASE ml_server TO ml_server;
SQL
echo "Database setup complete"
