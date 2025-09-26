#!/bin/bash

# Script setup Nginx cho domain api.donnhasach.vn
set -e

DOMAIN="api.donnhasach.vn"
EMAIL="your-email@example.com"  # Thay đổi email của bạn

echo "🚀 Setting up Nginx for domain: $DOMAIN"

# Kiểm tra Nginx đã cài chưa
if ! command -v nginx &> /dev/null; then
    echo "❌ Nginx chưa được cài đặt. Cài đặt Nginx trước:"
    echo "sudo apt update && sudo apt install nginx -y"
    exit 1
fi

echo "✅ Nginx đã được cài đặt"

# Tạo thư mục certbot
sudo mkdir -p /var/www/certbot

# Copy cấu hình Nginx
echo "📋 Copying Nginx configuration..."
sudo cp nginx-site.conf /etc/nginx/sites-available/api.donnhasach.vn

# Enable site
sudo ln -sf /etc/nginx/sites-available/api.donnhasach.vn /etc/nginx/sites-enabled/

# Test nginx config (chỉ HTTP trước)
echo "📝 Creating temporary HTTP-only config for SSL setup..."
sudo tee /etc/nginx/sites-available/api.donnhasach.vn.temp > /dev/null << 'EOF'
server {
    listen 80;
    server_name api.donnhasach.vn;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Sử dụng config tạm thời
sudo cp /etc/nginx/sites-available/api.donnhasach.vn.temp /etc/nginx/sites-enabled/api.donnhasach.vn

# Test nginx config
sudo nginx -t
if [ $? -ne 0 ]; then
    echo "❌ Nginx configuration error!"
    exit 1
fi

echo "✅ Nginx configuration is valid"

# Reload nginx
sudo systemctl reload nginx

echo "🔒 Requesting SSL certificate from Let's Encrypt..."

# Cài đặt certbot nếu chưa có
if ! command -v certbot &> /dev/null; then
    echo "📦 Installing certbot..."
    sudo apt update
    sudo apt install certbot python3-certbot-nginx -y
fi

# Request SSL certificate
sudo certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN

if [ $? -eq 0 ]; then
    echo "✅ SSL certificate obtained successfully!"
    
    # Restore full config with SSL
    echo "🔄 Applying full SSL configuration..."
    sudo cp nginx-site.conf /etc/nginx/sites-enabled/api.donnhasach.vn
    
    # Test config again
    sudo nginx -t && sudo systemctl reload nginx
    
    echo "🎉 Setup completed successfully!"
    echo "🌐 Your API is now available at: https://$DOMAIN"
    
    # Cleanup
    sudo rm -f /etc/nginx/sites-available/api.donnhasach.vn.temp
else
    echo "❌ Failed to obtain SSL certificate"
    echo "💡 Make sure:"
    echo "   1. Domain $DOMAIN points to this server's IP"
    echo "   2. Port 80 is accessible from internet"
    echo "   3. No firewall blocking the domain"
    exit 1
fi

echo ""
echo "📝 Next steps:"
echo "1. Update email in this script: $EMAIL"
echo "2. Test your API: curl https://$DOMAIN/docs"
echo "3. Setup auto-renewal: sudo crontab -e"
echo "   Add: 0 12 * * * certbot renew --quiet && systemctl reload nginx" 