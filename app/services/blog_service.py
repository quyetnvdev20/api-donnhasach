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
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lấy danh sách bài viết blog
        
        Args:
            page: Trang hiện tại (bắt đầu từ 1)
            limit: Số bài viết mỗi trang
            search: Từ khóa tìm kiếm
            
        Returns:
            Dict chứa danh sách bài viết và metadata
        """
        try:
            # Tính offset
            offset = (page - 1) * limit
            
            # Build query điều kiện
            where_clause = "1=1"
            
            if search:
                search_escaped = search.replace("'", "''")  # Escape single quotes
                where_clause += " AND (bp.name ->> 'vi_VN' ILIKE '%{}%' OR bp.subtitle ->> 'vi_VN' ILIKE '%{}%' OR bp.content ->> 'vi_VN' ILIKE '%{}%')".format(
                    search_escaped, search_escaped, search_escaped
                )
            
            # Query lấy danh sách bài viết
            posts_query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.content ->> 'vi_VN' as content,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    TO_CHAR(bp.create_date, 'DD/MM/YYYY HH24:MI') as create_date,
                    TO_CHAR(bp.write_date, 'DD/MM/YYYY HH24:MI') as write_date,
                    bp.visits,
                    bt.name ->> 'vi_VN' as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE {}
                ORDER BY bp.published_date DESC NULLS LAST, bp.create_date DESC
                LIMIT {} OFFSET {}
            '''.format(where_clause, limit, offset)
            
            # Query đếm tổng số bài viết
            count_query = '''
                SELECT COUNT(*) as total
                FROM blog_post bp
                WHERE {}
            '''.format(where_clause)
            
            # Thực hiện queries
            posts_result = await PostgresDB.execute_query(posts_query)
            result = []
            for item in posts_result:
                vals = {
                    'id': item.get('id'),
                    'title': item.get('title'),
                    'subtitle': item.get('subtitle'),
                    'content': item.get('content'),
                    'create_date': item.get('create_date'),
                    'write_date': item.get('write_date'),
                    'published_date': item.get('published_date'),
                    'blog_id': item.get('blog_id'),
                    'blog_name': item.get('blog_name'),
                    'visits': item.get('visits'),
                }
                result.append(vals)

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
            detail_query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.content ->> 'vi_VN' as content,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    TO_CHAR(bp.create_date, 'DD/MM/YYYY HH24:MI') as create_date,
                    TO_CHAR(bp.write_date, 'DD/MM/YYYY HH24:MI') as write_date,
                    bp.visits,
                    bt.name ->> 'vi_VN' as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.id = {}
            '''.format(post_id)
            
            result = await PostgresDB.execute_query(detail_query)
            
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
                "data": post
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
            query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.content ->> 'vi_VN' as content,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    TO_CHAR(bp.create_date, 'DD/MM/YYYY HH24:MI') as create_date,
                    TO_CHAR(bp.write_date, 'DD/MM/YYYY HH24:MI') as write_date,
                    bp.visits,
                    bt.name ->> 'vi_VN' as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                WHERE bp.blog_id = {} 
                    AND bp.id != {}
                    AND bp.website_published = true
                ORDER BY bp.published_date DESC
                LIMIT {}
            '''.format(blog_id, post_id, limit)
            
            result = await PostgresDB.execute_query(query)
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
            query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.content ->> 'vi_VN' as content,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    TO_CHAR(bp.create_date, 'DD/MM/YYYY HH24:MI') as create_date,
                    TO_CHAR(bp.write_date, 'DD/MM/YYYY HH24:MI') as write_date,
                    bp.visits,
                    bt.name ->> 'vi_VN' as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.website_published = true
                    AND bp.visits > 0
                ORDER BY bp.visits DESC
                LIMIT {}
            '''.format(limit)
            
            result = await PostgresDB.execute_query(query)
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
            update_query = '''
                UPDATE blog_post 
                SET visits = COALESCE(visits, 0) + 1,
                    write_date = NOW()
                WHERE id = {}
            '''.format(post_id)
            
            await PostgresDB.execute_query(update_query)
            
        except Exception as e:
            logger.error(f"Error incrementing visits for post {post_id}: {str(e)}")

    @staticmethod
    async def get_posts_by_category(
        category_id: int,
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Lấy bài viết theo category
        
        Args:
            category_id: ID của category
            page: Trang hiện tại
            limit: Số bài viết mỗi trang
            
        Returns:
            Dict chứa danh sách bài viết theo category
        """
        try:
            # Tính offset
            offset = (page - 1) * limit
            
            # Query lấy danh sách bài viết theo category
            posts_query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.content ->> 'vi_VN' as content,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    TO_CHAR(bp.create_date, 'DD/MM/YYYY HH24:MI') as create_date,
                    TO_CHAR(bp.write_date, 'DD/MM/YYYY HH24:MI') as write_date,
                    bp.visits,
                    bt.name ->> 'vi_VN' as blog_name,
                    bt.id as blog_id
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.blog_id = {}
                ORDER BY bp.published_date DESC NULLS LAST, bp.create_date DESC
                LIMIT {} OFFSET {}
            '''.format(category_id, limit, offset)
            
            # Query đếm tổng số bài viết theo category
            count_query = '''
                SELECT COUNT(*) as total
                FROM blog_post bp
                WHERE bp.blog_id = {}
            '''.format(category_id)
            
            # Thực hiện queries
            posts_result = await PostgresDB.execute_query(posts_query)
            count_result = await PostgresDB.execute_query(count_query)
            
            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit
            
            # Format response
            return {
                "success": True,
                "data": posts_result,
                "current_page": page,
                "per_page": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
            
        except Exception as e:
            logger.error(f"Error getting posts by category: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy bài viết theo category: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_trending_posts(days: int = 7, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Lấy bài viết trending trong X ngày gần đây
        
        Args:
            days: Số ngày gần đây
            limit: Số bài viết
            
        Returns:
            List bài viết trending
        """
        try:
            query = '''
                SELECT 
                    bp.id,
                    bp.name ->> 'vi_VN' as title,
                    bp.subtitle ->> 'vi_VN' as subtitle,
                    bp.teaser ->> 'vi_VN' as teaser,
                    TO_CHAR(bp.published_date, 'DD/MM/YYYY HH24:MI') as published_date,
                    bp.visits,
                    bp.cover_properties,
                    bt.name ->> 'vi_VN' as blog_name,
                    (bp.visits * 0.7 + COALESCE(bp.visits, 0) * 0.3) as trending_score
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.website_published = true 
                    AND bp.published_date >= NOW() - INTERVAL '{} days'
                ORDER BY trending_score DESC
                LIMIT {}
            '''.format(days, limit)
            
            result = await PostgresDB.execute_query(query)
            return result
            
        except Exception as e:
            logger.error(f"Error getting trending posts: {str(e)}")
            return []

    @staticmethod
    async def get_category_stats() -> List[Dict[str, Any]]:
        """
        Thống kê theo category
        
        Returns:
            List thống kê category
        """
        try:
            query = '''
                SELECT 
                    bt.name ->> 'vi_VN' as category_name,
                    COUNT(*) as total_posts,
                    SUM(bp.visits) as total_views,
                    AVG(bp.visits) as avg_views_per_post
                FROM blog_post bp
                LEFT JOIN blog_blog bt ON bp.blog_id = bt.id
                WHERE bp.website_published = true
                GROUP BY bt.id, bt.name
                ORDER BY total_posts DESC
            '''
            
            result = await PostgresDB.execute_query(query)
            return result
            
        except Exception as e:
            logger.error(f"Error getting category stats: {str(e)}")
            return [] 