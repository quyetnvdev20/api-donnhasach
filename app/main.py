from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .api.v1.endpoints import session, image

app = FastAPI(
    title="ACG XM Service",
    description="Service xử lý ảnh giấy bảo hiểm xe máy",
    version="1.0.0",
    openapi_tags=[
        {"name": "sessions", "description": "Session management operations"},
        {"name": "images", "description": "Image processing operations"},
    ],
)

# Thêm cấu hình security scheme cho OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Thêm security scheme cho Bearer token
    openapi_schema["components"] = {
        "securitySchemes": {
            "Bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter JWT Bearer token"
            }
        }
    }
    
    # Áp dụng security cho tất cả endpoints
    openapi_schema["security"] = [{"Bearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router, prefix="/api/v1", tags=["sessions"])
app.include_router(image.router, prefix="/api/v1", tags=["images"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 