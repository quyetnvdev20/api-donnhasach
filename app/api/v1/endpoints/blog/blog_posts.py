from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional
import logging
from app.services.blog_service import BlogService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/posts", summary="Lấy danh sách bài viết blog")
async def get_blog_posts(
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    limit: int = Query(10, ge=1, le=100, description="Số bài viết mỗi trang (tối đa 100)"),
    status: Optional[str] = Query("published", description="Trạng thái bài viết (published, draft)"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm trong tiêu đề, phụ đề, nội dung")
):
    """
    Lấy danh sách bài viết blog từ Odoo
    
    - **page**: Trang hiện tại (mặc định: 1)
    - **limit**: Số bài viết mỗi trang (mặc định: 10, tối đa: 100)
    - **status**: Trạng thái bài viết (mặc định: published)
    - **search**: Từ khóa tìm kiếm (tùy chọn)
    
    Returns:
        - posts: Danh sách bài viết
        - pagination: Thông tin phân trang
    """
    try:
        result = await BlogService.get_blog_posts(
            page=page,
            limit=limit,
            status=status,
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
            "data": result["data"]
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
        - post: Thông tin chi tiết bài viết
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
        
        post = result["data"]["post"]
        
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
            "data": {
                "post": post,
                "related_posts": related_posts
            }
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
        - posts: Danh sách bài viết phổ biến
    """
    try:
        posts = await BlogService.get_popular_posts(limit=limit)
        
        return {
            "success": True,
            "message": "Lấy bài viết phổ biến thành công",
            "data": {
                "posts": posts,
                "total": len(posts)
            }
        }
        
    except Exception as e:
        logger.error(f"Error in get_popular_posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi lấy bài viết phổ biến"
        )


@router.get("/search", summary="Tìm kiếm bài viết")
async def search_blog_posts(
    q: str = Query(..., min_length=1, description="Từ khóa tìm kiếm"),
    page: int = Query(1, ge=1, description="Số trang"),
    limit: int = Query(10, ge=1, le=100, description="Số bài viết mỗi trang")
):
    """
    Tìm kiếm bài viết theo từ khóa
    
    - **q**: Từ khóa tìm kiếm (bắt buộc)
    - **page**: Trang hiện tại (mặc định: 1)
    - **limit**: Số bài viết mỗi trang (mặc định: 10, tối đa: 100)
    
    Returns:
        - posts: Danh sách bài viết tìm được
        - pagination: Thông tin phân trang
        - search_term: Từ khóa đã tìm kiếm
    """
    try:
        result = await BlogService.search_posts(
            keyword=q,
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
            "message": f"Tìm kiếm bài viết với từ khóa '{q}' thành công",
            "data": {
                **result["data"],
                "search_term": q
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_blog_posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Có lỗi xảy ra khi tìm kiếm bài viết"
        ) 