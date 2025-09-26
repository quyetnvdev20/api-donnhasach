from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
import logging
from app.services.blog_service import BlogService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/posts", summary="Lấy danh sách bài viết blog")
async def get_blog_posts(
        search: Optional[str] = None,
        limit: int = 10,
        page: int = 1,
):
    """
    Lấy danh sách bài viết blog từ Odoo
    
    - **page**: Trang hiện tại (mặc định: 1)
    - **limit**: Số bài viết mỗi trang (mặc định: 10, tối đa: 100)
    - **search**: Từ khóa tìm kiếm (tùy chọn)
    
    Returns:
        - success: Trạng thái thành công
        - data: Danh sách bài viết
        - current_page: Trang hiện tại
        - limit: Số bài viết mỗi trang
        - total: Tổng số bài viết
        - total_pages: Tổng số trang
    """
    try:
        result = await BlogService.get_blog_posts(
            page=page,
            limit=limit,
            search=search
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "message": "Lấy danh sách bài viết thành công",
            "data": result["data"],
            "current_page": result["current_page"],
            "limit": result["limit"],
            "total": result["total"],
            "total_pages": result["total_pages"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_blog_posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy danh sách bài viết"
        )


@router.get("/posts/{post_id}", summary="Lấy chi tiết bài viết blog")
async def get_blog_post_detail(
    post_id: int = Path(..., gt=0, description="ID của bài viết")
):
    """
    Lấy chi tiết bài viết blog theo ID
    
    - **post_id**: ID của bài viết cần lấy chi tiết
    
    Returns:
        - success: Trạng thái thành công
        - data: Thông tin chi tiết bài viết
        - related_posts: Danh sách bài viết liên quan (nếu có)
    """
    try:
        # Lấy chi tiết bài viết
        result = await BlogService.get_blog_post_detail(post_id)
        
        if not result["success"]:
            if result["error"] == "Không tìm thấy bài viết":
                raise HTTPException(
                    status_code=404,
                    detail="Không tìm thấy bài viết"
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=result["error"]
                )
        
        post = result["data"]
        
        # Lấy bài viết liên quan (nếu có blog_id)
        related_posts = []
        if post.get("blog_id"):
            related_posts = await BlogService.get_related_posts(
                post_id=post_id,
                blog_id=post["blog_id"],
                limit=5
            )
        
        return {
            "success": True,
            "message": "Lấy chi tiết bài viết thành công",
            "data": post,
            "related_posts": related_posts
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_blog_post_detail: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy chi tiết bài viết"
        )


@router.get("/posts/popular", summary="Lấy bài viết phổ biến")
async def get_popular_posts(
    limit: int = Query(10, ge=1, le=50, description="Số bài viết phổ biến (tối đa 50)")
):
    """
    Lấy danh sách bài viết phổ biến (theo lượt xem)
    
    - **limit**: Số bài viết phổ biến cần lấy (mặc định: 10, tối đa: 50)
    
    Returns:
        - success: Trạng thái thành công
        - data: Danh sách bài viết phổ biến
        - total: Tổng số bài viết
        - limit: Số bài viết được lấy
    """
    try:
        posts = await BlogService.get_popular_posts(limit=limit)
        
        return {
            "success": True,
            "message": "Lấy bài viết phổ biến thành công",
            "data": posts,
            "total": len(posts),
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error in get_popular_posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy bài viết phổ biến"
        )


@router.get("/category/{category_id}/posts", summary="Lấy bài viết theo category")
async def get_posts_by_category(
    category_id: int = Path(..., gt=0, description="ID của category"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(10, ge=1, le=100, description="Số bài viết mỗi trang")
):
    """
    Lấy bài viết theo category
    
    - **category_id**: ID của category
    - **page**: Trang hiện tại (mặc định: 1)
    - **limit**: Số bài viết mỗi trang (mặc định: 10, tối đa: 100)
    
    Returns:
        - success: Trạng thái thành công
        - data: Danh sách bài viết theo category
        - category_id: ID của category
        - current_page: Trang hiện tại
        - limit: Số bài viết mỗi trang
        - total: Tổng số bài viết
        - total_pages: Tổng số trang
    """
    try:
        result = await BlogService.get_posts_by_category(
            category_id=category_id,
            page=page,
            limit=limit
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "message": f"Lấy bài viết theo category {category_id} thành công",
            "data": result["data"],
            "category_id": category_id,
            "current_page": result["current_page"],
            "per_page": result["per_page"],
            "total": result["total"],
            "total_pages": result["total_pages"],
            "has_next": result["has_next"],
            "has_prev": result["has_prev"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_posts_by_category: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy bài viết theo category"
        )


@router.get("/posts/trending", summary="Lấy bài viết trending")
async def get_trending_posts(
    days: int = Query(7, ge=1, le=30, description="Số ngày gần đây (tối đa 30)"),
    limit: int = Query(10, ge=1, le=50, description="Số bài viết (tối đa 50)")
):
    """
    Lấy bài viết trending trong X ngày gần đây
    
    - **days**: Số ngày gần đây (mặc định: 7, tối đa: 30)
    - **limit**: Số bài viết (mặc định: 10, tối đa: 50)
    
    Returns:
        - success: Trạng thái thành công
        - data: Danh sách bài viết trending
        - total: Tổng số bài viết
        - days: Số ngày đã lọc
        - limit: Số bài viết được lấy
    """
    try:
        posts = await BlogService.get_trending_posts(days=days, limit=limit)
        
        return {
            "success": True,
            "message": f"Lấy bài viết trending {days} ngày gần đây thành công",
            "data": posts,
            "total": len(posts),
            "days": days,
            "limit": limit
        }
        
    except Exception as e:
        logger.error(f"Error in get_trending_posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy bài viết trending"
        )


@router.get("/stats/categories", summary="Thống kê theo category")
async def get_category_stats():
    """
    Lấy thống kê bài viết theo category
    
    Returns:
        - success: Trạng thái thành công
        - data: Thống kê theo từng category
        - total_categories: Tổng số categories
    """
    try:
        stats = await BlogService.get_category_stats()
        
        return {
            "success": True,
            "message": "Lấy thống kê category thành công",
            "data": stats,
            "total_categories": len(stats)
        }
        
    except Exception as e:
        logger.error(f"Error in get_category_stats: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy thống kê category"
        ) 