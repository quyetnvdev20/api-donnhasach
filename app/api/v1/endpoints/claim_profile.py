from fastapi import APIRouter, Depends, HTTPException, status, Body
import logging
from ...deps import get_current_user
from sqlalchemy.orm import Session
from ....database import get_db
from ....config import settings, odoo
from ....schemas.claim_profile import AssignAppraisalRequest, AssignAppraisalResponse, ApproveLeaveSceneRequest, ApproveLeaveSceneResponse

router = APIRouter()
logger = logging.getLogger(__name__)





@router.post("/{profile_id}/assign-appraiser", response_model=AssignAppraisalResponse)
async def assign_appraiser(
    profile_id: int,
    request: AssignAppraisalRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Điều chuyển giám định viên cho hồ sơ
    
    Parameters:
    - profile_id: ID của hồ sơ cần điều chuyển
    - request: Thông tin giám định viên được điều chuyển
    
    Returns:
    - Kết quả điều chuyển
    """
    try:
        # Gọi API của Odoo để điều chuyển giám định viên
        response = await odoo.call_method_post(
            record_id=profile_id,
            model='insurance.claim.profile',
            method='assign_appraisal_profile_api',
            token=current_user.odoo_token,
            kwargs={
                'user_id': request.user_id,
                'branch_id': request.branch_id,
            }
        )
        return {
            "success": True,
            "message": "Điều chuyển giám định viên thành công"
        }
    
    except Exception as e:
        logger.error(f"Error assigning appraiser: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Điều chuyển giám định viên thất bại: {str(e)}"
        )
    
    
@router.post("/{profile_id}/approve-leave-scene", response_model=ApproveLeaveSceneResponse)
async def approve_leave_scene(
    profile_id: int,
    request: ApproveLeaveSceneRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Duyệt rời hiện trường cho hồ sơ bồi thường
    
    Parameters:
    - profile_id: ID của hồ sơ bồi thường
    - request: Thông tin người duyệt rời hiện trường
    
    Returns:
    - Kết quả duyệt rời hiện trường
    """
    try:
        # Gọi API của Odoo để duyệt rời hiện trường
        response = await odoo.call_method_post(
            record_id=profile_id,
            model='insurance.claim.profile',
            method='approve_leave_scene_api',
            token=current_user.odoo_token,
            kwargs={
                'user_receive_id': request.user_receive_id,
            }
        )
        
        return {
            "success": True,
            "message": "Duyệt rời hiện trường thành công"
        }
    
    except Exception as e:
        logger.error(f"Error approving leave scene: {str(e)}")
        raise e  
    
    



