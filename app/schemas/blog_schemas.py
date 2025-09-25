from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class BlogPostBase(BaseModel):
    """Schema cơ bản cho blog post"""
    id: int
    title: str
    subtitle: Optional[str] = None
    teaser: Optional[str] = None
    website_published: bool
    published_date: Optional[datetime] = None
    create_date: datetime
    write_date: datetime
    visits: Optional[int] = 0
    blog_name: Optional[str] = None
    blog_id: Optional[int] = None


class BlogPostList(BlogPostBase):
    """Schema cho danh sách blog posts (không bao gồm content đầy đủ)"""
    website_meta_title: Optional[str] = None
    website_meta_description: Optional[str] = None
    cover_properties: Optional[str] = None


class BlogPostDetail(BlogPostBase):
    """Schema cho chi tiết blog post (bao gồm content đầy đủ)"""
    content: Optional[str] = None
    website_meta_title: Optional[str] = None
    website_meta_description: Optional[str] = None
    website_meta_keywords: Optional[str] = None
    cover_properties: Optional[str] = None
    blog_description: Optional[str] = None


class PaginationInfo(BaseModel):
    """Schema cho thông tin phân trang"""
    current_page: int = Field(..., description="Trang hiện tại")
    per_page: int = Field(..., description="Số items mỗi trang")
    total: int = Field(..., description="Tổng số items")
    total_pages: int = Field(..., description="Tổng số trang")
    has_next: bool = Field(..., description="Có trang tiếp theo không")
    has_prev: bool = Field(..., description="Có trang trước không")


class BlogPostListResponse(BaseModel):
    """Schema cho response danh sách blog posts"""
    success: bool = True
    message: str
    data: dict = Field(..., example={
        "posts": [],
        "pagination": {
            "current_page": 1,
            "per_page": 10,
            "total": 0,
            "total_pages": 0,
            "has_next": False,
            "has_prev": False
        }
    })


class BlogPostDetailResponse(BaseModel):
    """Schema cho response chi tiết blog post"""
    success: bool = True
    message: str
    data: dict = Field(..., example={
        "post": {},
        "related_posts": []
    })


class PopularPostsResponse(BaseModel):
    """Schema cho response bài viết phổ biến"""
    success: bool = True
    message: str
    data: dict = Field(..., example={
        "posts": [],
        "total": 0
    })


class SearchResponse(BaseModel):
    """Schema cho response tìm kiếm"""
    success: bool = True
    message: str
    data: dict = Field(..., example={
        "posts": [],
        "pagination": {},
        "search_term": ""
    })


class ErrorResponse(BaseModel):
    """Schema cho error response"""
    success: bool = False
    detail: str = Field(..., description="Thông tin lỗi")
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "detail": "Có lỗi xảy ra"
            }
        } 