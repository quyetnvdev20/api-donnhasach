from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
import os
from typing import Optional

router = APIRouter()

# Đường dẫn đến thư mục chứa file cấu hình
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_DIR = os.path.join(BASE_DIR, "config_file")

@router.get("/.well-known/{system_type}", 
           response_class=FileResponse,
           description="Get well-known configuration file for Android/iOS")
async def get_well_known_file(
    system_type: str,
) -> FileResponse:
    """
    Endpoint to get well-known configuration files for Android/iOS app associations.
    
    Args:
        system_type (str): Type of system (android/ios)
        
    Returns:
        FileResponse: Configuration file for the specified system
        
    Raises:
        HTTPException: If system type is invalid or file not found
    """
    file_mapping = {
        "assetlinks.json": "assetlinks.json",
        "apple-app-site-association": "apple-app-site-association.apple-app-site-association"
    }
    
    filename = file_mapping.get(system_type)
    file_path = os.path.join(CONFIG_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Configuration file for {system_type} not found"
        )

    return FileResponse(
        file_path, 
        media_type="application/json",
        filename=filename
    )
