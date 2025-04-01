import functools
import logging
import traceback
from typing import Callable, Any, Optional, Type, Union
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
def handle_task_exception(
    task_model: Optional[Type] = None,
    session_factory: Optional[Callable[[], Session]] = None
):
    """
    Decorator để xử lý exception cho các task worker.
    
    Args:
        task_model: Model database để cập nhật trạng thái
        session_factory: Hàm tạo session database
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(task_id: Union[str, int], *args, **kwargs):
            if not task_model or not session_factory:
                return func(task_id, *args, **kwargs)
            
            db = session_factory()
            try:
                # Lấy task từ database
                task = db.query(task_model).filter(task_model.id == task_id).first()
                if not task:
                    logger.error(f"Không tìm thấy task với ID: {task_id}")
                    return
                
                # Cập nhật trạng thái đang xử lý
                task.state = "processing"
                db.add(task)
                db.commit()
                
                # Thực thi hàm gốc
                result = func(task_id, *args, **kwargs)
                
                # Cập nhật trạng thái hoàn thành
                task = db.query(task_model).filter(task_model.id == task_id).first()
                if task and task.state != "failed":  # Chỉ cập nhật nếu không bị lỗi
                    task.state = "completed"
                    db.add(task)
                    db.commit()
                
                return result
            except Exception as e:
                # Log lỗi
                error_detail = traceback.format_exc()
                logger.error(f"Lỗi trong task {func.__name__} với ID {task_id}: {str(e)}\n{error_detail}")
                
                # Cập nhật trạng thái lỗi
                try:
                    task = db.query(task_model).filter(task_model.id == task_id).first()
                    if task:
                        task.state = "failed"
                        task.error_message = f"{func.__name__}: {str(e)}"
                        db.add(task)
                        db.commit()
                except Exception as db_error:
                    logger.error(f"Không thể cập nhật trạng thái: {str(db_error)}")
                    db.rollback()
                
                # Raise lại exception
                raise
            finally:
                db.close()
        
        return wrapper
    
    return decorator 