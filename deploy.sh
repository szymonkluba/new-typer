#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/opc/typer"
cd "$APP_DIR"

echo "Pulling latest code..."
git pull origin main

echo "Updating static files for nginx..."
sudo cp -r "$APP_DIR/app/static/"* /var/www/typer/static/
sudo chcon -R -t httpd_sys_content_t /var/www/typer/static/

echo "Building and restarting containers..."
docker compose build
docker compose up -d

echo "Waiting for health check..."
sleep 5
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "Deployment successful - app is healthy"
else
    echo "WARNING: Health check failed"
    docker compose logs --tail=50
    exit 1
fi

echo "Done."
