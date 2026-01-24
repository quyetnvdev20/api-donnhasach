import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)


class CategoryService:
    """Service xử lý business logic cho blog posts từ Odoo"""

    @staticmethod
    async def get_category_service(
            page: int = 1,
            limit: int = 10,
            search: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            # Tính offset
            offset = (page - 1) * limit

            # Build query điều kiện
            where_clause = "1=1"

            if search:
                where_clause += " AND pc.name  ILIKE '%{}%' ".format( search )

            query = '''
                select pc.id, pc.name, pc.active, pc.icon, pc.url_image, is_recurring_service, description_detail from product_category pc where pc.is_service_main is true and {}
                LIMIT {} OFFSET {}
            '''.format(where_clause, limit, offset)

            # Query đếm tổng số bài viết
            count_query = '''
                SELECT COUNT(*) as total
                from product_category pc where pc.is_service_main is true and {}
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
            logger.error(f"Error getting category: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách dịch vụ: {str(e)}",
                "data": None
            }
