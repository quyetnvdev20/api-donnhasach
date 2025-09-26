#!/bin/bash

# Script để renew SSL certificate tự động
set -e

echo "🔄 Checking and renewing SSL certificates..."

# Renew certificates
docker compose run --rm certbot renew

# Reload nginx to use new certificates
docker compose restart nginx

echo "✅ SSL certificate renewal completed!"
echo "📅 Next renewal check: $(date -d '+60 days' '+%Y-%m-%d')" 