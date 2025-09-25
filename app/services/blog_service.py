import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)


class BlogService:
    """Service xử lý business logic cho blog posts từ Odoo"""
    
    @staticmethod
    async def get_blog_posts(
        page: int = 1,
        limit: int = 10,
        status: Optional[str] = "published",
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lấy danh sách bài viết blog
        
        Args:
            page: Trang hiện tại (bắt đầu từ 1)
            limit: Số bài viết mỗi trang
            status: Trạng thái bài viết (published, draft, etc.)
            search: Từ khóa tìm kiếm
            
        Returns:
            Dict chứa danh sách bài viết và metadata
        """
        try:
            # Tính offset
            offset = (page - 1) * limit
            
            # Build query điều kiện
            where_conditions = []
            params = {}
            
            if status:
                where_conditions.append("bp.website_published = %(status)s")
                params["status"] = status == "published"
                
            if search:
                where_conditions.append("""
                    (bp.name ILIKE %(search)s 
                     OR bp.subtitle ILIKE %(search)s 
                     OR bp.content ILIKE %(search)s)
                """)
                params["search"] = f"%{search}%"
            
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            # Query lấy danh sách bài viết
            posts_query = f"""
                SELECT 
                    bp.id,
                    bp.name as title,
                    bp.subtitle,
                    bp.teaser,
                    bp.content,
                    bp.website_published,
                    bp.published_date,
                    bp.create_date,
                    bp.write_date,
                    bp.website_meta_title,
                    bp.website_meta_description,
                    bp.cover_properties,
                    bp.visits,
                    bt.name as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE {where_clause}
                ORDER BY bp.published_date DESC NULLS LAST, bp.create_date DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """
            
            # Query đếm tổng số bài viết
            count_query = f"""
                SELECT COUNT(*) as total
                FROM blog_post bp
                WHERE {where_clause}
            """
            
            # Thực hiện queries
            params.update({"limit": limit, "offset": offset})
            
            posts_result = await PostgresDB.execute_query(posts_query, params)
            count_result = await PostgresDB.execute_query(count_query, params)
            
            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit
            
            # Format response
            return {
                "success": True,
                "data": {
                    "posts": posts_result,
                    "pagination": {
                        "current_page": page,
                        "per_page": limit,
                        "total": total,
                        "total_pages": total_pages,
                        "has_next": page < total_pages,
                        "has_prev": page > 1
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting blog posts: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách bài viết: {str(e)}",
                "data": None
            }
    
    @staticmethod
    async def get_blog_post_detail(post_id: int) -> Dict[str, Any]:
        """
        Lấy chi tiết bài viết blog theo ID
        
        Args:
            post_id: ID của bài viết
            
        Returns:
            Dict chứa thông tin chi tiết bài viết
        """
        try:
            # Query lấy chi tiết bài viết
            detail_query = """
                SELECT 
                    bp.id,
                    bp.name as title,
                    bp.subtitle,
                    bp.teaser,
                    bp.content,
                    bp.website_published,
                    bp.published_date,
                    bp.create_date,
                    bp.write_date,
                    bp.website_meta_title,
                    bp.website_meta_description,
                    bp.website_meta_keywords,
                    bp.cover_properties,
                    bp.visits,
                    bt.name as blog_name,
                    bt.id as blog_id,
                    bt.description as blog_description
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.id = %(post_id)s
            """
            
            result = await PostgresDB.execute_query(detail_query, {"post_id": post_id})
            
            if not result:
                return {
                    "success": False,
                    "error": "Không tìm thấy bài viết",
                    "data": None
                }
            
            post = result[0]
            
            # Tăng lượt xem (optional)
            await BlogService._increment_visits(post_id)
            
            return {
                "success": True,
                "data": {
                    "post": post
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting blog post detail: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy chi tiết bài viết: {str(e)}",
                "data": None
            }
    
    @staticmethod
    async def get_related_posts(post_id: int, blog_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Lấy bài viết liên quan
        
        Args:
            post_id: ID bài viết hiện tại
            blog_id: ID blog
            limit: Số bài viết liên quan
            
        Returns:
            List bài viết liên quan
        """
        try:
            query = """
                SELECT 
                    bp.id,
                    bp.name as title,
                    bp.subtitle,
                    bp.teaser,
                    bp.published_date,
                    bp.visits,
                    bp.cover_properties
                FROM blog_post bp
                WHERE bp.blog_id = %(blog_id)s 
                    AND bp.id != %(post_id)s
                    AND bp.website_published = true
                ORDER BY bp.published_date DESC
                LIMIT %(limit)s
            """
            
            result = await PostgresDB.execute_query(query, {
                "blog_id": blog_id,
                "post_id": post_id,
                "limit": limit
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting related posts: {str(e)}")
            return []
    
    @staticmethod
    async def get_popular_posts(limit: int = 10) -> List[Dict[str, Any]]:
        """
        Lấy bài viết phổ biến (theo lượt xem)
        
        Args:
            limit: Số bài viết
            
        Returns:
            List bài viết phổ biến
        """
        try:
            query = """
                SELECT 
                    bp.id,
                    bp.name as title,
                    bp.subtitle,
                    bp.teaser,
                    bp.published_date,
                    bp.visits,
                    bp.cover_properties,
                    bt.name as blog_name
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.website_published = true
                    AND bp.visits > 0
                ORDER BY bp.visits DESC
                LIMIT %(limit)s
            """
            
            result = await PostgresDB.execute_query(query, {"limit": limit})
            return result
            
        except Exception as e:
            logger.error(f"Error getting popular posts: {str(e)}")
            return []
    
    @staticmethod
    async def _increment_visits(post_id: int) -> None:
        """
        Tăng lượt xem bài viết
        
        Args:
            post_id: ID bài viết
        """
        try:
            update_query = """
                UPDATE blog_post 
                SET visits = COALESCE(visits, 0) + 1,
                    write_date = NOW()
                WHERE id = %(post_id)s
            """
            
            await PostgresDB.execute_query(update_query, {"post_id": post_id})
            
        except Exception as e:
            logger.error(f"Error incrementing visits for post {post_id}: {str(e)}")
    
    @staticmethod
    async def search_posts(
        keyword: str,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Tìm kiếm bài viết
        
        Args:
            keyword: Từ khóa tìm kiếm
            page: Trang hiện tại
            limit: Số bài viết mỗi trang
            
        Returns:
            Dict chứa kết quả tìm kiếm
        """
        return await BlogService.get_blog_posts(
            page=page,
            limit=limit,
            status="published",
            search=keyword
        ) 