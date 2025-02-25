# Claim AI

## Giới thiệu
Claim AI: Luồng AI Giám định chi tiết

## Yêu cầu hệ thống
- Python 3.8+
- PostgreSQL 14+
- RabbitMQ 3+
- Docker và Docker Compose (nếu sử dụng Docker)

## Cài đặt

### Chuẩn bị môi trường
1. Clone repository:
```
git clone https://gitlab.wilad.vn/tasco-insurance/acg/acg-xm.git
cd acg-xm
```

2. Tạo và kích hoạt môi trường ảo (tùy chọn nhưng khuyến nghị):
```
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Cài đặt các thư viện cần thiết:
```
pip install -r requirements.txt
```

4. Tạo file `.env` với các biến môi trường cần thiết:
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5437/acg_xm
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key
```

## Chạy ứng dụng

### Phương pháp 1: Sử dụng Docker (khuyến nghị)

1. Đảm bảo Docker và Docker Compose đã được cài đặt trên máy của bạn.

2. Khởi động tất cả các dịch vụ:
```
docker-compose up
```

3. Để chạy ở chế độ nền:
```
docker-compose up -d
```

4. Để dừng các dịch vụ:
```
docker-compose down
```

5. Để xem logs:
```
docker-compose logs -f
```

6. Để xem logs của một dịch vụ cụ thể:
```
docker-compose logs -f api
docker-compose logs -f image_processor
docker-compose logs -f policy_creator
docker-compose logs -f session-processor
```

### Phương pháp 2: Chạy Native

#### Chuẩn bị
1. Đảm bảo PostgreSQL đang chạy và có thể truy cập được qua URL trong file `.env`
2. Đảm bảo RabbitMQ đang chạy và có thể truy cập được qua URL trong file `.env`

#### Chạy từng thành phần

Dự án bao gồm nhiều thành phần có thể chạy độc lập. Sử dụng file `run.py` để chạy các thành phần:

1. Chạy API server:
```
python run.py --component api
```

2. Chạy Image Processor worker:
```
python run.py --component image-processor
```

3. Bỏ qua việc chạy migrations (thêm flag `--skip-migrations`):
```
python run.py --component api --skip-migrations
```

**Lưu ý**: Trong môi trường phát triển, bạn nên chạy từng thành phần trong các terminal riêng biệt để dễ theo dõi log.

## Cấu trúc dự án
- `app/`: Thư mục chính chứa mã nguồn
  - `main.py`: Entry point cho API server
  - `workers/`: Chứa các worker xử lý
    - `image_processor.py`: Worker xử lý hình ảnh
- `alembic/`: Chứa các migration cho cơ sở dữ liệu
- `docker-compose.yml`: Cấu hình Docker Compose
- `Dockerfile`: Cấu hình Docker
- `run.py`: Script để chạy ứng dụng native

## API Documentation
Sau khi khởi động API server, bạn có thể truy cập tài liệu API tại:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Phát triển

### Migrations
Để tạo migration mới:
```
alembic revision --autogenerate -m "Mô tả thay đổi"
```

Để áp dụng migration:
```
alembic upgrade head
```

## Liên hệ và hỗ trợ
Nếu bạn có bất kỳ câu hỏi hoặc gặp vấn đề, vui lòng liên hệ với team phát triển.

## Trạng thái dự án
Dự án đang trong quá trình phát triển.

# acg-xm
