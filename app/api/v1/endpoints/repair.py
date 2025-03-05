from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...deps import get_current_user
from ....database import get_db
from ....schemas.repair import RepairPlanApprovalRequest, RepairPlanApprovalResponse, RepairPlanListResponse, \
    RepairPlanDetailResponse, RepairPlanApproveRequest, RepairPlanApproveResponse, RepairPlanRejectRequest, \
    RepairPlanRejectResponse

router = APIRouter()


@router.put("/{repair_id}/submit-repair-plan-approval",
            response_model=RepairPlanApprovalResponse,
            status_code=status.HTTP_200_OK)
async def submit_repair_plan_approval(
        repair_id: int,
        repair_plan: RepairPlanApprovalRequest,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> dict[str, int]:
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )

        return {
            "id": repair_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/repair-plan-awaiting-list",
            response_model=RepairPlanListResponse,
            status_code=status.HTTP_200_OK)
async def get_repair_plan_awaiting_list(
        state: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> RepairPlanListResponse:
    """
    Get list of repair plans awaiting approval
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )

        # Mock data - replace with actual database query later
        formatted_plans = [
            {
                "file_name": "HS202403001",
                "vehicle_info": "Toyota Camry 2.5Q 2020 - 30A12345",
                "owner_name": "Nguyễn Văn A",
                "location_damage": "Đường Bình Kỳ, Ngũ Hành sơn, TP Đà Nẵng",
                "repair_garage_location": {
                    "id": "867",
                    "name": "Mitsubishi Quảng Nam"
                },
                "total_cost": {
                    "value": 1500000,
                    "color_code": "FF5733"
                },
                "submitter": "Nguyễn Văn B",
                "inspection_date": "01/03/2024",
                "status": {
                    "name": "Chờ duyệt",
                    "code": "PASC001",
                    "color_code": "F1C40F"
                },
                "label": {
                    "name": "Nhãn A",
                    "code": "LABEL001",
                    "color_code": "7D3C98"
                }
            }
        ]

        return RepairPlanListResponse(
            data=formatted_plans
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{repair_id}/repair-plan-awaiting-detail",
            response_model=RepairPlanDetailResponse,
            status_code=status.HTTP_200_OK)
async def get_repair_plan_awaiting_detail(
        repair_id: str,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> RepairPlanDetailResponse:
    """
    Get detailed information of a repair plan awaiting approval
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )

        # Mock data - replace with actual database query later
        repair_plan_detail = {
            "file_name": "HS202403001",
            "contract_number": "HD202301234",
            "vehicle_info": "Toyota Camry 2.5Q 2020 - 30A12345",
            "repair_garage_location": {
                "id": "867",
                "name": "Mitsubishi Quảng Nam"
            },
            "inspection_date": "01/03/2024",
            "approval_deadline": "05/03/2024",
            "owner_name": "Nguyễn Văn A",
            "owner_phone": "0901234567",
            "status": {
                "name": "Chờ duyệt",
                "code": "PASC001",
                "color_code": "F1C40F"
            },
            "btn_approve": True,
            "btn_reject": True,
            "approval_history": [
                {
                    "reason": "Chi phí hợp lý",
                    "approval_time": "01/03/2024"
                }
            ],
            "repair_plan_details": [
                {
                    "name": "thay cản trước",
                    "item": {
                        "name": "Cản trước",
                        "id": 246
                    },
                    "type": {
                        "name": "Sơn",
                        "code": "paint",
                        "color_code": "ABC123"
                    },
                    "garage_price": 1000000,
                    "suggested_price": 900000,
                    "discount_percentage": 10
                }
            ],
            "amount_subtotal": 2345687834,
            "amount_discount": 100000,
            "amount_untaxed_total": 546467657
        }

        return RepairPlanDetailResponse(
            data=repair_plan_detail
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/approve",
            response_model=RepairPlanApproveResponse,
            status_code=status.HTTP_200_OK)
async def approve_repair_plan(
    request: RepairPlanApproveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> RepairPlanApproveResponse:
    """
    Approve a repair plan
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        
        return RepairPlanApproveResponse(
            id=int(request.repair_id)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/reject",
            response_model=RepairPlanRejectResponse,
            status_code=status.HTTP_200_OK)
async def reject_repair_plan(
    request: RepairPlanRejectRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> RepairPlanRejectResponse:
    """
    Reject a repair plan
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        
        return RepairPlanRejectResponse(
            id=int(request.repair_id)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
