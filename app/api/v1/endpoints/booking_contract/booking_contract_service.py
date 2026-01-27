import logging
from typing import Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class BookingContractService:

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

