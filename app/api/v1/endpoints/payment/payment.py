from fastapi import APIRouter, HTTPException, Depends, Body, Path, Header
from typing import Optional
import logging
from .payment_service import PaymentService
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/payos/webhook", summary="Webhook nhận callback từ PayOS")
async def payos_webhook(
        data: dict = Body(...),
):
    """
    Webhook endpoint để nhận callback từ PayOS
    PayOS sẽ gửi POST request với:
    - Body: webhook data
    - Header: x-payos-signature (chữ ký để verify)
    
    Endpoint này có thể xử lý webhook cho bất kỳ loại thanh toán nào
    """
    try:
        # Lấy signature từ header (nếu có)
        result = await PaymentService.handle_payos_webhook(
            webhook_data=data,
        )
        
        if not result.get('success'):
            logger.warning(f"PayOS webhook failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get('error')
            }
        
        return {
            "success": True,
            "message": result.get('message', 'Webhook processed successfully'),
            "data": result
        }
    except Exception as e:
        logger.error(f"Unexpected error in payos_webhook: {str(e)}")
        # Vẫn trả về 200 để PayOS không retry
        return {
            "success": False,
            "error": str(e)
        }

