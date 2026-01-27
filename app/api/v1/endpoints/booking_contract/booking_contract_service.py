import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class BookingContractService:

    @classmethod
    async def get_booking_contracts(
        cls,
        current_user: UserObject,
        page: int = 1,
        limit: int = 10,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lấy danh sách hợp đồng định kỳ"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='get_booking_contracts_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'partner_id': current_user.partner_id,
                    'page': page,
                    'limit': limit,
                    'from_date': from_date.strftime('%Y-%m-%d') if from_date else None,
                    'to_date': to_date.strftime('%Y-%m-%d') if to_date else None,
                    'state': state,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error getting booking contracts: {str(e)}")
            raise

    @classmethod
    async def get_booking_contract_detail(
        cls,
        contract_id: int,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Lấy chi tiết hợp đồng định kỳ"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='get_booking_contract_detail_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error getting booking contract detail: {str(e)}")
            raise

    @classmethod
    async def check_schedule_price(
        cls,
        contract_id: int,
        schedule_id: int,
        new_date: str,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Kiểm tra giá khi đổi lịch"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='check_schedule_price_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'schedule_id': schedule_id,
                    'new_date': new_date,
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error checking schedule price: {str(e)}")
            raise

    @classmethod
    async def update_schedule_date(
        cls,
        contract_id: int,
        schedule_id: int,
        data: dict,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Đổi lịch schedule.booking.calendar"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='update_schedule_date_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'schedule_id': schedule_id,
                    'new_date': data.get('new_date'),
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error updating schedule date: {str(e)}")
            raise

    @classmethod
    async def create_booking_contract(cls, data: dict, current_user: UserObject):
        """Tạo hợp đồng dọn dẹp định kỳ"""
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='booking.contract',
            method='create_periodic_booking_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

