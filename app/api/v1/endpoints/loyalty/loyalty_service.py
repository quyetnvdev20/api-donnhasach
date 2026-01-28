import logging
from typing import Dict, Any, Optional
from app.schemas.user import UserObject
from app.config import settings, odoo
from app.utils.erp_db import PostgresDB

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

    @staticmethod
    async def get_loyalty_programs_list_service(
            page: int = 1,
            limit: int = 10,
            search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lấy danh sách các chương trình khuyến mại (không cần đăng nhập)
        Lọc theo date_from và date_to: lấy các chương trình đang hiệu lực
        Bao gồm cả các chương trình không có date_from hoặc date_to (vĩnh viễn)
        """
        try:
            # Tính offset
            offset = (page - 1) * limit

            # Build query điều kiện
            # Lọc theo date: date_from <= hôm nay và date_to >= hôm nay
            # Hoặc NULL (không giới hạn thời gian)
            where_clause = """lp.active = true 
                AND (
                    (lp.date_from IS NULL OR lp.date_from <= CURRENT_DATE)
                    AND (lp.date_to IS NULL OR lp.date_to >= CURRENT_DATE)
                )"""

            if search:
                # Search trong JSONB field name
                where_clause += " AND (coalesce(lp.name ->> 'vi_VN', lp.name ->> 'en_US') ILIKE '%{}%')".format(search)

            query = '''
                SELECT 
                    lp.id,
                    coalesce(lp.name ->> 'vi_VN', lp.name ->> 'en_US') as name,
                    lp.active,
                    '',
                    lp.sequence
                FROM loyalty_program lp
                WHERE {}
                ORDER BY lp.sequence ASC, lp.id ASC
                LIMIT {} OFFSET {}
            '''.format(where_clause, limit, offset)

            # Query đếm tổng số
            count_query = '''
                SELECT COUNT(*) as total
                FROM loyalty_program lp
                WHERE {}
            '''.format(where_clause)

            # Thực hiện queries
            result = await PostgresDB.execute_query(query)
            count_result = await PostgresDB.execute_query(count_query)

            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit

            return {
                "success": True,
                "data": result,
                "current_page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }

        except Exception as e:
            logger.error(f"Error getting loyalty programs list: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách chương trình khuyến mại: {str(e)}",
                "data": None
            }

