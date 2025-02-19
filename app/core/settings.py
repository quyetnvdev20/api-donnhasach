from enum import Enum

class SessionStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    CLOSED = "closed"
    FAILED = "failed"

class ImageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    DONE = "done"

# Các constant khác có thể thêm vào đây
MAX_RETRY_COUNT = 3
IMAGE_UPLOAD_PATH = "uploads/images" 