# ACG XM Service

Service xử lý ảnh giấy bảo hiểm xe máy sử dụng OpenAI Vision API.

## Tính năng

- Upload và xử lý ảnh giấy bảo hiểm
- Trích xuất thông tin từ ảnh sử dụng OpenAI Vision API
- Tạo đơn bảo hiểm từ thông tin trích xuất
- Authentication với Keycloak
- Message queue với RabbitMQ
- Database migrations với Alembic

## Cài đặt môi trường phát triển

### Yêu cầu

- Docker và Docker Compose
- Python 3.9+
- Git

### Các bước cài đặt

1. Copy file môi trường:

```bash
cp .env.example .env
```

2. Cập nhật các biến môi trường trong file .env:

```bash
nano .env
```

3. Chạy Docker Compose:

```bash
docker-compose up --build
```


## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Sessions

- `POST /api/v1/sessions` - Tạo session mới
- `PUT /api/v1/sessions/{session_id}/open` - Mở session
- `PUT /api/v1/sessions/{session_id}/close` - Đóng session
- `GET /api/v1/sessions/{session_id}` - Lấy thông tin session
- `GET /api/v1/sessions` - Lấy danh sách sessions

### Images

- `POST /api/v1/sessions/{session_id}/images` - Upload ảnh vào session
- `GET /api/v1/sessions/{session_id}/images` - Lấy danh sách ảnh của session
- `GET /api/v1/images/{image_id}` - Lấy thông tin chi tiết ảnh
- `GET /api/v1/sessions/{session_id}/urls` - Lấy danh sách URLs ảnh của session

## Authentication

Service sử dụng Keycloak để xác thực. Tất cả API endpoints đều yêu cầu Bearer token hợp lệ.

## Database Migrations

### Tạo migration mới