from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .api.v1.endpoints import session, image, insurance_detail, policy_create
app = FastAPI(
    title="ACG XM Service",
    description="Service xử lý ảnh giấy bảo hiểm xe máy",
    version="1.0.0",
    openapi_tags=[
        {"name": "sessions", "description": "Session management operations"},
        {"name": "images", "description": "Image processing operations"},
        {"name": "insurance_details", "description": "Insurance detail operations"},
    ],
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router, prefix="/api/v1", tags=["sessions"])
app.include_router(image.router, prefix="/api/v1", tags=["images"])
app.include_router(
    insurance_detail.router,
    prefix="/api/v1",
    tags=["insurance_details"]
)
app.include_router(policy_create.router, prefix="/api/v1", tags=["policy_create"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"} 
