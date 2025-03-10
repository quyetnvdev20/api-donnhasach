from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Union

# Mapping các message lỗi validation sang tiếng Việt
ERROR_MESSAGES_VI = {
    "field required": "là trường bắt buộc",
    "value is not a valid integer": "phải là số nguyên",
    "value is not a valid float": "phải là số thực",
    "value is not a valid boolean": "phải là giá trị boolean",
    "value is not a valid dict": "phải là đối tượng",
    "value is not a valid list": "phải là mảng",
    "value is not a valid email address": "không phải là email hợp lệ",
    "value is not a valid enumeration member": "không phải là giá trị hợp lệ trong enum",
    "ensure this value has at least": "giá trị phải có ít nhất",
    "ensure this value has at most": "giá trị không được vượt quá",
    "string does not match regex": "không đúng định dạng",
    "value could not be parsed to a boolean": "không thể chuyển đổi sang boolean",
    "value is not a valid date": "không phải là ngày hợp lệ",
    "value is not a valid datetime": "không phải là thời gian hợp lệ",
    "none is not an allowed value": "không được phép là null",
    "value is not none": "phải là null",
    "ensure this value contains at least": "phải chứa ít nhất",
    "ensure this value contains at most": "không được chứa quá",
}

async def validation_exception_handler(request: Request, exc: Union[RequestValidationError, ValidationError]):
    """
    Xử lý lỗi validation từ cả request và response models
    """
    error_messages = []
    for error in exc.errors():
        field_name = " -> ".join([str(x) for x in error["loc"]])
        error_msg = error.get("msg", "")
        
        # Dịch message lỗi sang tiếng Việt nếu có trong mapping
        for en_msg, vi_msg in ERROR_MESSAGES_VI.items():
            if en_msg in error_msg.lower():
                error_msg = vi_msg
                break
                
        error_messages.append(f"Trường {field_name} {error_msg}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Dữ liệu không hợp lệ",
            "errors": error_messages
        }
    ) 