from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import os
import json
from typing import Optional

router = APIRouter()

# Đường dẫn đến thư mục chứa file cấu hình
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_DIR = os.path.join(BASE_DIR, "config_file")

@router.get("/.well-known/{system_type}", 
           response_class=JSONResponse,
           description="Get well-known configuration file for Android/iOS")
async def get_well_known_file(
    system_type: str,
) -> JSONResponse:
    """
    Endpoint to get well-known configuration files for Android/iOS app associations.
    
    Args:
        system_type (str): Type of system (android/ios)
        
    Returns:
        JSONResponse: Configuration file content
        
    Raises:
        HTTPException: If system type is invalid or file not found
    """
    file_mapping = {
        "assetlinks.json": "assetlinks.json",
        "apple-app-site-association": "apple-app-site-association.apple-app-site-association"
    }
    
    filename = file_mapping.get(system_type)
    if not filename:
        raise HTTPException(
            status_code=404, 
            detail=f"Invalid system type: {system_type}"
        )

    file_path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Configuration file for {system_type} not found"
        )

    try:
        with open(file_path, 'r') as f:
            config_data = json.load(f)
            return JSONResponse(
                content=config_data,
                media_type="application/json"
            )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON configuration file"
        )
