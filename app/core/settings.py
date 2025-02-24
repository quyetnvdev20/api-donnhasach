from enum import Enum
import os
class SessionStatus(str, Enum):
    NEW = "new"
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    INVALID = "invalid"

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