# Hướng dẫn Deploy lên Server Ubuntu

## Thông tin Server
- **IP**: 171.244.139.130
- **OS**: Ubuntu
- **Domains**: 
  - `api.donnhasach.vn` → FastAPI (cổng 8888)
  - `api.cleanhome.vn` → FastAPI (cổng 8888) - cùng project
- **Port**: 8888

## Các bước Deploy (Thủ công)

### 1. Cài đặt Nginx (nếu chưa có)

```bash
sudo apt update
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 2. Copy file cấu hình Nginx cho api.donnhasach.vn

```bash
cd /home/Api/api-donnhasach
sudo cp nginx/api.donnhasach.vn.conf /etc/nginx/sites-available/api.donnhasach.vn.conf
```

### 2b. Copy file cấu hình Nginx cho api.cleanhome.vn

```bash
cd /home/Api/api-donnhasach
sudo cp nginx/api.cleanhome.vn.conf /etc/nginx/sites-available/api.cleanhome.vn.conf
```

### 3. Kích hoạt cấu hình Nginx

```bash
# Kích hoạt api.donnhasach.vn
sudo ln -s /etc/nginx/sites-available/api.donnhasach.vn.conf /etc/nginx/sites-enabled/api.donnhasach.vn.conf

# Kích hoạt api.cleanhome.vn
sudo ln -s /etc/nginx/sites-available/api.cleanhome.vn.conf /etc/nginx/sites-enabled/api.cleanhome.vn.conf
```

### 4. Kiểm tra cấu hình Nginx

```bash
# Kiểm tra cấu hình có hợp lệ không
sudo nginx -t
```

Nếu thấy thông báo `nginx: configuration file /etc/nginx/nginx.conf test is successful` thì cấu hình đúng.

### 5. Reload Nginx để áp dụng cấu hình

```bash
sudo systemctl reload nginx
```

### 6. Khởi động FastAPI

Chạy FastAPI trên cổng 8888:

```bash
cd /home/quyetnv/DonNhaSachProject/fastapi/api-donnhasach
python run.py --component api
```

Hoặc nếu dùng virtual environment:

```bash
cd /home/quyetnv/DonNhaSachProject/fastapi/api-donnhasach
source venv/bin/activate  # Nếu có venv
python run.py --component api
```

### 7. Cấu hình Firewall (nếu cần)

```bash
# Cho phép HTTP và HTTPS
sudo ufw allow 'Nginx Full'
# hoặc
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Kiểm tra firewall
sudo ufw status
```

### 8. Cấu hình DNS

Đảm bảo domain `api.donnhasach.vn` đã được trỏ về IP server:
- **A Record**: `api.donnhasach.vn` → `171.244.139.130`

Kiểm tra DNS:
```bash
dig api.donnhasach.vn
# hoặc
nslookup api.donnhasach.vn
```

### 9. Cài đặt SSL Certificate (Let's Encrypt)

Sau khi DNS đã trỏ đúng, cài đặt SSL:

```bash
# Cài đặt certbot
sudo apt install certbot python3-certbot-nginx -y

# Lấy SSL certificate
sudo certbot --nginx -d api.donnhasach.vn

# Certbot sẽ tự động cập nhật cấu hình nginx
# Sau đó bỏ comment phần SSL trong file nginx/api.donnhasach.vn.conf
```

### 10. Kiểm tra

```bash
# Kiểm tra nginx đang chạy
sudo systemctl status nginx

# Kiểm tra FastAPI có đang chạy trên cổng 8888
sudo netstat -tlnp | grep 8888
# hoặc
sudo ss -tlnp | grep 8888

# Test API từ server
curl http://localhost:8888/docs
curl http://api.donnhasach.vn/docs

# Test với header x-api-key
curl -H "x-api-key: YOUR_KEY" http://api.donnhasach.vn/api/v1/health
```

### 11. Xem Logs

```bash
# Nginx access logs
sudo tail -f /var/log/nginx/api.donnhasach.vn.access.log

# Nginx error logs
sudo tail -f /var/log/nginx/api.donnhasach.vn.error.log

# FastAPI logs (hiển thị trong terminal nơi chạy python run.py)
```

## Troubleshooting

### Nginx không khởi động
```bash
sudo nginx -t  # Kiểm tra cấu hình
sudo systemctl status nginx
sudo journalctl -u nginx -n 50
```

### FastAPI không nhận được request
- Kiểm tra FastAPI có đang chạy trên cổng 8888:
  ```bash
  sudo netstat -tlnp | grep 8888
  # hoặc
  sudo ss -tlnp | grep 8888
  ```

- Kiểm tra firewall:
  ```bash
  sudo ufw status
  ```

### Header x-api-key không được truyền
- Đảm bảo trong file nginx có dòng:
  ```
  underscores_in_headers on;
  proxy_set_header X-Api-Key $http_x_api_key;
  ```

- Reload nginx sau khi sửa:
  ```bash
  sudo nginx -t && sudo systemctl reload nginx
  ```

## Tóm tắt các lệnh cần chạy trên Server

**Trên server Ubuntu (171.244.139.130), chạy các lệnh sau:**

```bash
# 1. Copy cấu hình nginx
cd /home/quyetnv/DonNhaSachProject/fastapi/api-donnhasach
sudo cp nginx/api.donnhasach.vn.conf /etc/nginx/sites-available/api.donnhasach.vn.conf

# 2. Kích hoạt site
sudo ln -s /etc/nginx/sites-available/api.donnhasach.vn.conf /etc/nginx/sites-enabled/api.donnhasach.vn.conf

# 3. Kiểm tra cấu hình
sudo nginx -t

# 4. Reload nginx
sudo systemctl reload nginx

# 5. Chạy FastAPI (trong terminal riêng hoặc screen/tmux)
cd /home/quyetnv/DonNhaSachProject/fastapi/api-donnhasach
python run.py --component api
```

## Cấu trúc File

```
/home/Api/api-donnhasach/
├── nginx/
│   ├── api.donnhasach.vn.conf    # Cấu hình nginx cho api.donnhasach.vn
│   └── api.cleanhome.vn.conf     # Cấu hình nginx cho api.cleanhome.vn
└── README_DEPLOY.md              # File này
```

