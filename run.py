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

def run_alembic_migrations():
    """Chạy migration với Alembic"""
    logger.info("Đang chạy migrations...")
    try:
        # Sử dụng module thay vì lệnh trực tiếp
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        logger.info("Migrations hoàn tất")
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy migrations: {str(e)}")
        sys.exit(1)

def run_api():
    """Chạy API server với Uvicorn"""
    logger.info("Đang khởi động API server...")
    try:
        # Sử dụng module thay vì lệnh trực tiếp
        subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy API server: {str(e)}")
        sys.exit(1)

def run_image_processor():
    """Chạy worker xử lý ảnh"""
    logger.info("Đang khởi động Image Processor worker...")
    try:
        subprocess.run([sys.executable, "-m", "app.workers.image_processor"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy Image Processor: {str(e)}")
        sys.exit(1)

def run_policy_creator():
    """Chạy worker tạo policy"""
    logger.info("Đang khởi động Policy Creator worker...")
    try:
        subprocess.run([sys.executable, "-m", "app.workers.policy_creator"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy Policy Creator: {str(e)}")
        sys.exit(1)

def run_session_processor():
    """Chạy worker xử lý session"""
    logger.info("Đang khởi động Session Processor worker...")
    try:
        subprocess.run([sys.executable, "-m", "app.workers.session_processor"], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Lỗi khi chạy Session Processor: {str(e)}")
        sys.exit(1)

def check_environment():
    """Kiểm tra các biến môi trường cần thiết"""
    required_vars = ["DATABASE_URL", "RABBITMQ_URL", "OPENAI_API_KEY", "GOOGLE_API_KEY"]
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
    parser.add_argument("--component", choices=["api", "image-processor", "policy-creator", "session-processor", "all"], 
                        default="all", help="Thành phần cần chạy")
    parser.add_argument("--skip-migrations", action="store_true", help="Bỏ qua việc chạy migrations")
    parser.add_argument("--skip-checks", action="store_true", help="Bỏ qua việc kiểm tra môi trường và thư viện")
    
    args = parser.parse_args()
    
    # Kiểm tra môi trường và thư viện
    if not args.skip_checks:
        check_dependencies()
        check_environment()
    
    # Chạy migrations nếu cần
    if not args.skip_migrations:
        run_alembic_migrations()
    
    # Chạy thành phần được chỉ định
    if args.component == "api":
        run_api()
    elif args.component == "image-processor":
        run_image_processor()
    elif args.component == "policy-creator":
        run_policy_creator()
    elif args.component == "session-processor":
        run_session_processor()
    elif args.component == "all":
        logger.warning("Chạy tất cả các thành phần cùng lúc không được khuyến nghị trong môi trường phát triển.")
        logger.warning("Nên chạy từng thành phần riêng biệt trong các terminal khác nhau.")
        logger.info("Ví dụ:")
        logger.info("Terminal 1: python run.py --component api")
        logger.info("Terminal 2: python run.py --component image-processor --skip-migrations")
        
        choice = input("Bạn có muốn tiếp tục chạy tất cả các thành phần? (y/n): ")
        if choice.lower() != 'y':
            sys.exit(0)
            
        # Nếu người dùng muốn tiếp tục, chạy API (các worker nên được chạy riêng)
        run_api()

if __name__ == "__main__":
    main() 