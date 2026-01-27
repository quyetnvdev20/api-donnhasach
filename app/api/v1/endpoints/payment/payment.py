from fastapi import APIRouter, HTTPException, Depends, Body, Path, Header
from typing import Optional
import logging
from .payment_service import PaymentService
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/payos/{contract_id}/create-payment", summary="Tạo payment link từ PayOS")
async def create_payos_payment(
        contract_id: int = Path(..., description="ID hợp đồng"),
        payment_method_id: int = Body(..., description="ID phương thức thanh toán"),
        return_url: Optional[str] = Body(None, description="URL redirect sau khi thanh toán thành công"),
        cancel_url: Optional[str] = Body(None, description="URL redirect khi hủy thanh toán"),
        current_user=Depends(get_current_user),
):
    """
    Tạo payment link từ PayOS cho hợp đồng
    Có thể sử dụng cho bất kỳ loại hợp đồng nào (booking contract, booking, etc.)
    """
    try:
        result = await PaymentService.create_payos_payment_link(
            contract_id=contract_id,
            payment_method_id=payment_method_id,
            current_user=current_user,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Lỗi không xác định'))
        
        return {
            "success": True,
            "message": "Tạo payment link thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_payos_payment: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tạo payment link"
        )


@router.get("/payos/{contract_id}/status", summary="Lấy trạng thái thanh toán")
async def get_payment_status(
        contract_id: int = Path(..., description="ID hợp đồng"),
        current_user=Depends(get_current_user),
):
    """
    Lấy trạng thái thanh toán của hợp đồng
    Có thể sử dụng cho bất kỳ loại hợp đồng nào
    """
    try:
        result = await PaymentService.get_payment_status(
            contract_id=contract_id,
            current_user=current_user,
        )
        
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Lỗi không xác định'))
        
        return {
            "success": True,
            "message": "Lấy trạng thái thanh toán thành công",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_payment_status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy trạng thái thanh toán"
        )


@router.post("/payos/webhook", summary="Webhook nhận callback từ PayOS")
async def payos_webhook(
        data: dict = Body(...),
        x_payos_signature: Optional[str] = Header(None, alias="x-payos-signature"),
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
        signature = x_payos_signature or ""
        
        result = await PaymentService.handle_payos_webhook(
            webhook_data=data,
            signature=signature
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

