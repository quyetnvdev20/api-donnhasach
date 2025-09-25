# Docker Setup Guide

## 🐳 Cấu trúc Docker

Project sử dụng Docker để containerize FastAPI application và kết nối với các services có sẵn:

- **API**: FastAPI application (Blog microservice)
- **External Database**: Kết nối với PostgreSQL có sẵn
- **External Redis**: Kết nối với Redis có sẵn  

## 🚀 Quick Start

### 1. Setup môi trường

```bash
# Clone project
git clone <repository-url>
cd api-donnhasach

# Tạo file .env từ template
make dev-setup
# hoặc
cp env.example .env
```

### 2. Chỉnh sửa file .env

⚠️ **QUAN TRỌNG**: Mở file `.env` và cấu hình kết nối với database và Redis có sẵn:

```env
# Database có sẵn của bạn
DATABASE_URL=postgresql://username:password@your-db-host:5432/your_database
POSTGRES_DATABASE_URL=postgresql://username:password@your-db-host:5432/your_database

# Redis có sẵn của bạn  
REDIS_URL=redis://your-redis-host:6379

# Odoo connection (REQUIRED cho blog API)
ODOO_URL=http://your-odoo-server:8069
ODOO_TOKEN=your_odoo_token
```

### 3. Build và chạy

```bash
# Build API image
make build

# Start API service
make up

# Xem logs
make logs
```

## 📋 Available Commands

```bash
make help              # Hiển thị tất cả commands
make build             # Build API Docker image
make up                # Start API service
make down              # Stop API service
make restart           # Restart API service
make logs              # Show API logs
make clean             # Clean up containers
make shell             # Access API container
make status            # Check service status
make test-api          # Test API connection
make test-connections  # Test external DB/Redis connections
```

## 🌐 Endpoints

Sau khi start thành công:

- **API Documentation**: http://localhost:8000/docs
- **API Base URL**: http://localhost:8000/api/v1
- **Blog API**: http://localhost:8000/api/v1/blog/posts

> **Lưu ý**: Bạn cần cấu hình Nginx server có sẵn để proxy tới `http://localhost:8000`

## 📊 Blog API Endpoints

### Lấy danh sách bài viết
```http
GET /api/v1/blog/posts?page=1&limit=10&status=published
```

### Lấy chi tiết bài viết
```http
GET /api/v1/blog/posts/{post_id}
```

### Tìm kiếm bài viết
```http
GET /api/v1/blog/search?q=keyword&page=1
```

### Bài viết phổ biến
```http
GET /api/v1/blog/posts/popular?limit=10
```

## 🔧 Development

### Hot Reload
API service được cấu hình với `--reload` flag nên code changes sẽ tự động reload.

### Debug
```bash
# Access container shell
make shell

# View logs in real-time
make logs

# Check service health
make status

# Test API
make test-api

# Test external connections
make test-connections
```

## 🚀 Production Deployment

### Nginx Configuration (Server có sẵn)

Thêm vào Nginx config của server:

```nginx
upstream donnhasach-api {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    location /api/ {
        proxy_pass http://donnhasach-api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://donnhasach-api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Environment Variables for Production
```env
ENVIRONMENT=production
DEBUG=false
SENTRY_DSN=your_sentry_dsn
API_PORT=8000
```

## 🔍 Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check what's using the port
   lsof -i :8000
   
   # Change port in .env
   API_PORT=8001
   ```

2. **Database connection issues**
   ```bash
   # Test database connection
   make test-connections
   
   # Check API logs
   make logs
   
   # Verify .env configuration
   cat .env
   ```

3. **Build issues**
   ```bash
   # Clean build
   make clean
   make build
   ```

### Health Checks

```bash
# Check service health
make status

# Test API health
make test-api
curl http://localhost:8000/docs

# Test external connections
make test-connections
```

## 🔗 External Dependencies

Đảm bảo các services bên ngoài đã sẵn sàng:

### Database Requirements
- PostgreSQL với Odoo schema
- Bảng `blog_post` phải tồn tại
- User có quyền SELECT trên bảng blog

### Redis Requirements  
- Redis server accessible
- No authentication required (hoặc cấu hình trong REDIS_URL)

### Odoo Requirements
- Odoo server accessible
- Valid API token
- Blog module enabled

### Server Nginx Requirements
- Nginx đã cài đặt và chạy
- Có quyền chỉnh sửa config
- Port 8000 accessible từ Nginx

## 🔒 Security Notes

- Đảm bảo database credentials được bảo mật
- Cấu hình firewall để chỉ Nginx có thể access port 8000
- Regular security updates cho base images
- Không commit file `.env` vào repository

## 📞 Support

Nếu gặp vấn đề:
1. Check logs: `make logs`
2. Check service status: `make status`  
3. Test connections: `make test-connections`
4. Restart service: `make restart`
5. Clean rebuild: `make clean && make build && make up` 