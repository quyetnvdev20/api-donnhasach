#!/bin/bash

# Script để setup SSL certificate cho api.donnhasach.vn
set -e

DOMAIN="api.donnhasach.vn"
EMAIL="your-email@example.com"  # Thay đổi email của bạn

echo "🚀 Setting up SSL certificate for $DOMAIN"

# Tạo thư mục cần thiết
mkdir -p nginx/logs
mkdir -p certbot/conf
mkdir -p certbot/www

# Tạo nginx config tạm thời để lấy certificate
cat > nginx/nginx-temp.conf << EOF
events {
    worker_connections 1024;
}

http {
    server {
        listen 80;
        server_name $DOMAIN;
        
        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }
        
        location / {
            return 200 'Server is ready for SSL setup';
            add_header Content-Type text/plain;
        }
    }
}
EOF

echo "📋 Step 1: Starting temporary nginx for certificate generation"
# Backup original nginx config
if [ -f nginx/nginx.conf ]; then
    cp nginx/nginx.conf nginx/nginx.conf.backup
fi

# Use temporary config
cp nginx/nginx-temp.conf nginx/nginx.conf

# Start nginx temporarily
docker compose up -d nginx

echo "⏳ Waiting for nginx to start..."
sleep 10

echo "🔒 Step 2: Requesting SSL certificate from Let's Encrypt"
# Request certificate
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

echo "✅ Step 3: Certificate obtained successfully!"

# Restore original nginx config
if [ -f nginx/nginx.conf.backup ]; then
    cp nginx/nginx.conf.backup nginx/nginx.conf
    rm nginx/nginx.conf.backup
else
    echo "⚠️  Original nginx config not found, keeping current config"
fi

# Remove temporary config
rm -f nginx/nginx-temp.conf

echo "🔄 Step 4: Restarting services with SSL configuration"
docker compose down
docker compose up -d

echo "🎉 SSL setup completed!"
echo "🌐 Your API is now available at: https://$DOMAIN"
echo ""
echo "📝 Next steps:"
echo "1. Update the email in this script: $EMAIL"
echo "2. Make sure your domain $DOMAIN points to this server"
echo "3. Test your API: curl https://$DOMAIN/docs"
echo ""
echo "🔄 To renew certificates automatically, add this to crontab:"
echo "0 12 * * * cd $(pwd) && docker compose run --rm certbot renew && docker compose restart nginx" 