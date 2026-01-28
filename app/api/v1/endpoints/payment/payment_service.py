import logging
from typing import Dict, Any
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class PaymentService:
    """Service xử lý các tác vụ liên quan đến thanh toán (PayOS)"""

    @classmethod
    async def create_payos_payment_link(
        cls,
        contract_id: int,
        payment_method_id: int,
        current_user: UserObject,
        return_url: str = None,
        cancel_url: str = None,
    ) -> Dict[str, Any]:
        """
        Tạo payment link từ PayOS
        
        :param contract_id: ID hợp đồng
        :param payment_method_id: ID phương thức thanh toán
        :param current_user: User hiện tại
        :param return_url: URL redirect sau khi thanh toán thành công (optional)
        :param cancel_url: URL redirect khi hủy thanh toán (optional)
        :return: Dict với payment_link và qr_code
        """
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='create_payos_payment_link_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'partner_id': current_user.partner_id,
                    'payment_method_id': payment_method_id,
                    'return_url': return_url,
                    'cancel_url': cancel_url,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error creating PayOS payment link: {str(e)}")
            raise
    
    @classmethod
    async def handle_payos_webhook(cls, webhook_data: dict) -> Dict[str, Any]:
        """
        Xử lý webhook từ PayOS
        PayOS gửi signature trong webhook_data['signature'], không cần từ header
        
        :param webhook_data: Dữ liệu webhook từ PayOS (bao gồm signature)
        :return: Dict với kết quả xử lý
        """
        try:
            # Signature được lấy từ webhook_data['signature']
            signature = webhook_data.get('signature', '')
            
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='handle_payos_webhook_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'data': webhook_data,
                    'signature': signature,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error handling PayOS webhook: {str(e)}")
            raise
    
    @classmethod
    async def get_payment_status(
        cls,
        contract_id: int,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """
        Lấy trạng thái thanh toán của contract
        
        :param contract_id: ID hợp đồng
        :param current_user: User hiện tại
        :return: Dict với payment_status
        """
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='get_payment_status_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            raise

