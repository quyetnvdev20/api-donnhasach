import functools
import logging
import traceback
from typing import Callable, Any, Optional, Type, Union
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def handle_step_exception(
    db_model: Optional[Type] = None,
    id_attr: str = "id",
    state_attr: str = "state",
    error_message_attr: str = "error_message"
):
    """
    Decorator để xử lý exception và cập nhật trạng thái của step.
    
    Args:
        db_model: Model database để cập nhật trạng thái
        id_attr: Tên thuộc tính ID của đối tượng
        state_attr: Tên thuộc tính state của đối tượng
        error_message_attr: Tên thuộc tính error_message của đối tượng
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Xác định đối tượng cần cập nhật và session database
            obj = None
            db_session = None
            
            # Tìm đối tượng trong args hoặc kwargs
            for arg in args:
                if db_model and isinstance(arg, db_model):
                    obj = arg
                if isinstance(arg, Session):
                    db_session = arg
            
            for key, value in kwargs.items():
                if db_model and isinstance(value, db_model):
                    obj = value
                if key == "db" and isinstance(value, Session):
                    db_session = value
            
            # Nếu không tìm thấy đối tượng hoặc session, tiếp tục thực thi hàm
            if not obj or not db_session:
                return func(*args, **kwargs)
            
            try:
                # Thực thi hàm gốc
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                # Log lỗi
                error_detail = traceback.format_exc()
                logger.error(f"Lỗi trong step {func.__name__}: {str(e)}\n{error_detail}")
                
                # Cập nhật trạng thái của đối tượng
                try:
                    setattr(obj, state_attr, "failed")
                    setattr(obj, error_message_attr, f"{func.__name__}: {str(e)}")
                    
                    # Commit thay đổi vào database
                    db_session.add(obj)
                    db_session.commit()
                    
                    logger.info(f"Đã cập nhật trạng thái 'failed' cho {db_model.__name__} với {id_attr}={getattr(obj, id_attr)}")
                except Exception as db_error:
                    logger.error(f"Không thể cập nhật trạng thái: {str(db_error)}")
                    db_session.rollback()
                
                # Raise lại exception
                raise
        
        return wrapper
    
    return decorator


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