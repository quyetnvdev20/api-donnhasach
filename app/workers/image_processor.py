from app.utils.decorators import handle_step_exception, handle_task_exception
from app.models.image import ImageAnalysis
from app.database import get_db

# Ví dụ sử dụng decorator cho một step
@handle_step_exception(db_model=ImageAnalysis)
def process_image_step(image_analysis: ImageAnalysis, db):
    # Xử lý hình ảnh
    # Nếu có lỗi, decorator sẽ cập nhật trạng thái và lưu thông báo lỗi
    pass

# Ví dụ sử dụng decorator cho một task worker
@handle_task_exception(task_model=ImageAnalysis, session_factory=get_db)
def process_image_task(task_id: int):
    # Xử lý task
    # Decorator sẽ tự động cập nhật trạng thái của task
    pass 