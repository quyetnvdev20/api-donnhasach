import logging
from typing import Dict, Any
from app.schemas.user import UserObject
from app.config import settings, odoo
from app.utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)


class PaymentService:
    """Service xử lý các tác vụ liên quan đến thanh toán (PayOS)"""

    @classmethod
    async def create_payos_payment_contract_link(
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
        Xử lý webhook từ PayOS - hàm chung cho cả contract và booking
        PayOS gửi signature trong webhook_data['signature'], không cần từ header
        
        :param webhook_data: Dữ liệu webhook từ PayOS (bao gồm signature)
        :return: Dict với kết quả xử lý
        """
        try:
            # Signature được lấy từ webhook_data['signature']
            signature = webhook_data.get('signature', '')
            
            # Gọi hàm xử lý webhook chung từ payos.payment.history
            result = await odoo.call_method_not_record(
                model='payos.payment.history',
                method='handle_payos_webhook_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'webhook_data': webhook_data,
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
        Lấy trạng thái thanh toán của contract - Query trực tiếp từ database
        
        :param contract_id: ID hợp đồng
        :param current_user: User hiện tại
        :return: Dict với payment_status
        """
        try:
            query = '''
                SELECT 
                    bc.id as contract_id,
                    bc.payment_status,
                    bc.partner_id
                FROM booking_contract bc
                WHERE bc.id = {} AND bc.partner_id = {}
            '''.format(contract_id, current_user.partner_id)
            
            result = await PostgresDB.execute_query(query)
            
            if not result:
                return {
                    'success': False,
                    'error': 'Không tìm thấy hợp đồng hoặc bạn không có quyền truy cập',
                    'data': None
                }
            
            item = result[0]
            return {
                'success': True,
                'data': {
                    'contract_id': item.get('contract_id'),
                    'payment_status': item.get('payment_status', 'pending'),
                }
            }
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            return {
                'success': False,
                'error': f'Lỗi khi lấy trạng thái thanh toán: {str(e)}',
                'data': None
            }
    
    @classmethod
    async def create_payos_payment_link_booking(
        cls,
        booking_id: int,
        payment_method_id: int,
        current_user: UserObject,
        return_url: str = None,
        cancel_url: str = None,
    ) -> Dict[str, Any]:
        """
        Tạo payment link từ PayOS cho booking (calendar.event)
        
        :param booking_id: ID booking
        :param payment_method_id: ID phương thức thanh toán
        :param current_user: User hiện tại
        :param return_url: URL redirect sau khi thanh toán thành công (optional)
        :param cancel_url: URL redirect khi hủy thanh toán (optional)
        :return: Dict với payment_link và qr_code
        """
        try:
            result = await odoo.call_method_not_record(
                model='calendar.event',
                method='create_payos_payment_link_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'booking_id': booking_id,
                    'partner_id': current_user.partner_id,
                    'payment_method_id': payment_method_id,
                    'return_url': return_url,
                    'cancel_url': cancel_url,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error creating PayOS payment link for booking: {str(e)}")
            raise
    
    @classmethod
    async def get_payment_status_booking(
        cls,
        booking_id: int,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """
        Lấy trạng thái thanh toán của booking (calendar.event) - Query trực tiếp từ database
        
        :param booking_id: ID booking
        :param current_user: User hiện tại
        :return: Dict với payment_status
        """
        try:
            query = '''
                SELECT 
                    ce.id as booking_id,
                    ce.payment_status,
                    ce.partner_id
                FROM calendar_event ce
                WHERE ce.id = {} AND ce.partner_id = {}
            '''.format(booking_id, current_user.partner_id)
            
            result = await PostgresDB.execute_query(query)
            
            if not result:
                return {
                    'success': False,
                    'error': 'Không tìm thấy booking hoặc bạn không có quyền truy cập',
                    'data': None
                }
            
            item = result[0]
            return {
                'success': True,
                'data': {
                    'booking_id': item.get('booking_id'),
                    'payment_status': item.get('payment_status', 'pending'),
                }
            }
        except Exception as e:
            logger.error(f"Error getting payment status for booking: {str(e)}")
            return {
                'success': False,
                'error': f'Lỗi khi lấy trạng thái thanh toán: {str(e)}',
                'data': None
            }

