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
                select 
                    pc.id, 
                    pc.name, 
                    pc.active, 
                    pc.icon, 
                    pc.url_image, 
                    is_recurring_service, 
                    description_detail
                from product_category pc 
                where pc.is_service_main is true and {} 
                order by pc.sequence asc
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

    @staticmethod
    async def get_product_extra_service(
            category_id: int
    ) -> Dict[str, Any]:
        try:
            query = '''
                SELECT 
                    pp.id,
                    pt.name ->> 'vi_VN' as name,
                    COALESCE(pt.is_add_quantity, false) as is_add_quantity,
                    COALESCE(pt.list_price, 0) as list_price
                FROM product_category_product_product_extra_rel pcpp
                JOIN product_product pp ON pcpp.product_id = pp.id
                    join product_template pt on pp.product_tmpl_id = pt.id
                WHERE pcpp.category_id = {}
                ORDER BY pt.name
            '''.format(category_id)

            result = await PostgresDB.execute_query(query)

            return {
                "success": True,
                "data": result,
            }

        except Exception as e:
            logger.error(f"Error getting product extra: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách dịch vụ thêm: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_cleaning_script_service(
            category_id: int
    ) -> Dict[str, Any]:
        try:
            # Lấy cleaning_script_id từ category
            category_query = '''
                SELECT cleaning_script_id
                FROM product_category
                WHERE id = {}
            '''.format(category_id)
            
            category_result = await PostgresDB.execute_query(category_query)
            
            if not category_result or not category_result[0].get('cleaning_script_id'):
                return {
                    "success": True,
                    "data": None,
                }
            
            script_id = category_result[0]['cleaning_script_id']
            
            # Chỉ lấy các phòng (children của root) - bậc 2
            # Không lấy root (bậc 1) và không lấy children của phòng (bậc 3)
            query = '''
                SELECT 
                    cst.id,
                    cst.name,
                    cst.sequence,
                    cst.property_type,
                    cst.parent_id,
                    cst.is_room,
                    COALESCE(cst.task_items, '') as task_items
                FROM cleaning_script_template cst
                WHERE cst.parent_id = {}
                ORDER BY cst.sequence, cst.id
            '''.format(script_id)
            
            result = await PostgresDB.execute_query(query)
            
            if not result:
                return {
                    "success": True,
                    "data": [],
                }
            
            # Chuyển đổi task_items từ string sang mảng
            # Format: mỗi dòng là một công việc, có thể bắt đầu bằng "+" hoặc "-"
            rooms_data = []
            for row in result:
                task_items_list = []
                if row['task_items']:
                    # Tách theo dòng và lọc bỏ dòng trống
                    lines = [line.strip() for line in row['task_items'].split('\n') if line.strip()]
                    for line in lines:
                        # Bỏ dấu "+" hoặc "-" ở đầu nếu có
                        task = line.lstrip('+-').strip()
                        if task:
                            task_items_list.append(task)
                
                rooms_data.append({
                    'id': row['id'],
                    'name': row['name'],
                    'sequence': row['sequence'],
                    'property_type': row['property_type'],
                    'is_room': row['is_room'],
                    'task_items': task_items_list,
                    'parent_id': row.get('parent_id')
                })
            
            return {
                "success": True,
                "data": rooms_data,
            }

        except Exception as e:
            logger.error(f"Error getting cleaning script: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy kịch bản dọn nhà: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_employee_configs_service(
            category_id: int
    ) -> Dict[str, Any]:
        """
        Lấy danh sách cấu hình nhân viên theo category_id
        """
        try:
            query = '''
                SELECT 
                    pcec.id,
                    pcec.name,
                    pcec.employee_count,
                    pcec.duration_hours,
                    pcec.area
                FROM product_category_employee_config pcec
                WHERE pcec.category_id = {} AND pcec.active = true
                ORDER BY pcec.employee_count ASC, pcec.sequence ASC
            '''.format(category_id)

            result = await PostgresDB.execute_query(query)

            return {
                "success": True,
                "data": result if result else [],
            }

        except Exception as e:
            logger.error(f"Error getting employee configs: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy cấu hình nhân viên: {str(e)}",
                "data": None
            }
