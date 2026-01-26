import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo
from datetime import datetime
from app.api.deps import get_value_fields_selection
import locale

logger = logging.getLogger(__name__)


class MasterdatasService:

    @staticmethod
    async def get_ward(
            page: int = 1,
            limit: int = 10,
            search: Optional[str] = None,
            state_id: Optional[int] = None,

    ) -> Dict[str, Any]:
        try:
            # Tính offset
            offset = (page - 1) * limit

            # Build query điều kiện
            where_clause = "1=1"

            if search:
                where_clause += " AND rcw.name  ILIKE '%{}%' ".format(search)
            if state_id:
                where_clause += " AND rcw.state_id = {} ".format(state_id)

            query = '''
                select rcw.id, rcw.name from res_country_ward rcw where {}
                LIMIT {} OFFSET {}
            '''.format(where_clause, limit, offset)

            # Query đếm tổng số xã phường
            count_query = '''
                SELECT COUNT(*) as total
                from res_country_ward rcw where {}
            '''.format(where_clause)

            # Thực hiện queries
            posts_result = await PostgresDB.execute_query(query)

            count_result = await PostgresDB.execute_query(count_query)

            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit

            return {
                "success": True,
                "data": posts_result,
                "current_page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        except Exception as e:
            logger.error(f"Error getting: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách xã phường: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_state(
            page: int = 1,
            limit: int = 10,
            search: Optional[str] = None,

    ) -> Dict[str, Any]:
        try:
            # Tính offset
            offset = (page - 1) * limit

            # Build query điều kiện
            where_clause = "1=1"

            if search:
                where_clause += " AND rcs.name  ILIKE '%{}%' ".format(search)

            query = '''
                    select rcs.id, rcs.name from res_country_state rcs 
                    join res_country rc on rcs.country_id = rc.id
                    where rc.code = 'VN' and {}
                    LIMIT {} OFFSET {}
                '''.format(where_clause, limit, offset)

            # Query đếm tổng số TP
            count_query = '''
                    SELECT COUNT(*) as total
                        from res_country_state rcs 
                        join res_country rc on rcs.country_id = rc.id
                    where rc.code = 'VN' and  {}
                '''.format(where_clause)

            # Thực hiện queries
            posts_result = await PostgresDB.execute_query(query)

            count_result = await PostgresDB.execute_query(count_query)

            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit

            return {
                "success": True,
                "data": posts_result,
                "current_page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }
        except Exception as e:
            logger.error(f"Error getting: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách TP: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_periodic_packages() -> Dict[str, Any]:
        """Lấy danh sách gói định kỳ"""
        try:
            query = '''
                SELECT 
                    id,
                    name,
                    duration_months,
                    COALESCE(description, '') as description,
                    min_booking_count
                FROM periodic_package
                WHERE active = true
                ORDER BY duration_months
            '''
            
            result = await PostgresDB.execute_query(query)
            
            return {
                "success": True,
                "data": result,
            }
        except Exception as e:
            logger.error(f"Error getting periodic packages: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách gói định kỳ: {str(e)}",
                "data": None
            }
