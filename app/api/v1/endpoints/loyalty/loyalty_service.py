import logging
from typing import Dict, Any
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class LoyaltyService:

    @classmethod
    async def get_loyalty_programs(cls, data: dict, current_user: UserObject):
        """
        Lấy danh sách các chính sách bán hàng và chương trình khuyến mại
        """
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='loyalty.program',
            method='get_loyalty_programs_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

    @classmethod
    async def get_loyalty_program_by_card(cls, data: dict, current_user: UserObject):
        """
        Lấy chương trình khuyến mại theo mã card
        """
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='loyalty.program',
            method='get_loyalty_program_by_card_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

