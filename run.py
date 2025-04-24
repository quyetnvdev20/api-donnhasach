import os
import sys
import argparse
import subprocess
import logging
from dotenv import load_dotenv

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load biến môi trường từ file .env
load_dotenv()

def run_api():
    """Chạy API server với Uvicorn"""
    logger.info("Đang khởi động API server...")
    try:
        # Sử dụng module thay vì lệnh trực tiếp
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8079", "--reload"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy API server: {str(e)}")
        sys.exit(1)

def check_environment():
    """Kiểm tra các biến môi trường cần thiết"""
    required_vars = ["DATABASE_URL", "RABBITMQ_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Thiếu các biến môi trường: {', '.join(missing_vars)}")
        logger.error("Vui lòng tạo file .env với các biến môi trường cần thiết")
        sys.exit(1)
    
    logger.info("Đã kiểm tra các biến môi trường")

def check_dependencies():
    """Kiểm tra các thư viện cần thiết đã được cài đặt chưa"""
    required_packages = ["uvicorn", "alembic", "fastapi"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Thiếu các thư viện: {', '.join(missing_packages)}")
        logger.error("Vui lòng cài đặt các thư viện cần thiết: pip install -r requirements.txt")
        sys.exit(1)
    
    logger.info("Đã kiểm tra các thư viện cần thiết")

def main():
    """Hàm chính để chạy ứng dụng"""
    parser = argparse.ArgumentParser(description="Chạy các thành phần của ứng dụng")
    parser.add_argument("--component", choices=["api", "image-processor", "suggestion-pricelist-processor"],
                        default="api", help="Thành phần cần chạy")
    parser.add_argument("--skip-checks", action="store_true", help="Bỏ qua việc kiểm tra môi trường và thư viện")
    
    args = parser.parse_args()
    
    # Kiểm tra môi trường và thư viện
    if not args.skip_checks:
        check_dependencies()
        check_environment()
    
    # Chạy thành phần được chỉ định
    if args.component == "api":
        run_api()
    elif args.component == "all":
        logger.warning("Chạy tất cả các thành phần cùng lúc không được khuyến nghị trong môi trường phát triển.")
        logger.warning("Nên chạy từng thành phần riêng biệt trong các terminal khác nhau.")
        logger.info("Ví dụ:")
        logger.info("Terminal 1: python run.py --component api")

        choice = input("Bạn có muốn tiếp tục chạy tất cả các thành phần? (y/n): ")
        if choice.lower() != 'y':
            sys.exit(0)

        # Nếu người dùng muốn tiếp tục, chạy API (các worker nên được chạy riêng)
        run_api()

if __name__ == "__main__":
    main() 