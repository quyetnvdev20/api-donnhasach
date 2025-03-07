from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.repair import RepairPlanApprovalRequest, RepairPlanApprovalResponse, RepairPlanListResponse, \
    RepairPlanDetailResponse, RepairPlanApproveRequest, RepairPlanApproveResponse, RepairPlanRejectRequest, \
    RepairPlanRejectResponse, RepairCategory
import logging
from ....utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)

router = APIRouter()

STATE_COLOR = {
    "new": ("#84d9d8", "Mới"),
    "pending": ("#faad14", "Chờ duyệt"),
    "approved": ("#52c41a", "Đã duyệt"),
}

CATEGORIES_COLOR = {
    "parts": "#0958d9",
    "labor": "#d46b08",
    "paint": "#531dab",
}


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
        response = await odoo.call_method_post(
            record_id=repair_id,
            model='insurance.claim.solution.repair',
            method='submit_repair_plan_approval',
            token=current_user.get('token'),
            kwargs=repair_plan.model_dump()
        )
        if response.get("status_code") == status.HTTP_200_OK:
            return {'id': response.get("data")}
        else:
            raise Exception(response.get("message"))
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
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> RepairPlanListResponse:
    """
    Get list of repair plans awaiting approval with state in ('new', 'wait')
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        query = """
            select 
                a.id repair_id,
                a.state repair_state,
                to_char(e.date + INTERVAL '7 hours', 'dd/MM/yyyy HH24:MI') as inspection_date,
                a.price_subtotal,
                b.id as gara_id,
                rp.name gara_name,
                c.location_damage,
                c.name file_name,
                concat(rcb.name, ' ', rcm.name, ' ', ic.manufacturer_year, ' - ', ic.license_plate) as vehicle_info,
                rpu.name as submitter,
                ic.car_owner_name
            from insurance_claim_solution_repair a
            left join insurance_claim_appraisal_detail e on a.detailed_appraisal_id = e.id
            left join res_partner_gara b on a.gara_partner_id = b.id
            left join res_partner rp on b.partner_id = rp.id
            left join insurance_claim_profile c on a.new_claim_profile_id = c.id
            left join insurance_claim_receive d on c.insur_claim_id = d.id
            left join insurance_contract_certification icc on c.certification_id = icc.id
            left join insurance_contract ic on icc.contract_id = ic.id
            left join res_car_model rcm on rcm.id = ic.car_model_id
            left join res_car_brand rcb on rcb.id = ic.car_brand_id
            left join res_users ru on a.create_uid = ru.id
            left join res_partner rpu on ru.partner_id = rpu.id
            where a.state in ('new', 'pending')
        """

        params = []

        if state == 'cho_duyet':
            state = 'pending'

        query += """ and a.state = $1"""
        params.append(state)

        if search:
            query += """ and (a.name ILIKE $2 or c.name ILIKE $2 or a.object_name ILIKE $2)"""
            params.append(f"%{search}%")

        # Add ordering and pagination
        query += f"""
        ORDER BY a.id DESC
        LIMIT {int(limit)} OFFSET {int(offset)}
        """

        results = await PostgresDB.execute_query(query, params)

        formatted_plans = []

        for res in results:
            formatted_plans.append({
                "file_name": res.get('file_name'),
                "id": res.get('repair_id'),
                "vehicle_info": res.get('vehicle_info'),
                "owner_name": res.get('car_owner_name'),
                "location_damage": res.get('location_damage'),
                "repair_garage_location": {
                    "id": res.get('gara_id'),
                    "name": res.get('gara_name')
                },
                "total_cost": {
                    "value": int(res.get('price_subtotal')),
                    "color_code": "#52C41A"
                },
                "submitter": res.get('submitter'),
                "inspection_date": res.get('inspection_date'),
                "status": {
                    "name": STATE_COLOR.get(res.get('repair_state'))[1] if STATE_COLOR.get(res.get('repair_state')) else "Chờ duyệt",
                    "code": res.get('repair_state'),
                    "color_code": STATE_COLOR.get(res.get('repair_state'))[0] if STATE_COLOR.get(res.get('repair_state')) else "#faad14"
                },
                "label": {
                    "name": "Gấp",  # TODO chưa biết lấy dữ liệu ở đâu
                    "code": "LABEL001",
                    "color_code": "#f5222d"
                }
            })

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
        repair_id: int,
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

        query = """
            select 
                a.id repair_id,
                a.state repair_state,
                a.price_subtotal,
                b.id as gara_id,
                rp.name gara_name,
                COALESCE(c.location_damage, '') location_damage,
                to_char(e.date + INTERVAL '7 hours', 'dd/MM/yyyy HH24:MI') as inspection_date,
                c.name file_name,
                ic.name contract_number,
                concat(rcb.name, ' ', rcm.name, ' ', ic.manufacturer_year, ' - ', ic.license_plate) as vehicle_info,
                rpu.name as submitter,
                ic.car_owner_name,
                ic.car_owner_phone,
                a.price_total_propose,
                a.total_discount,
                a.price_subtotal,
                (select sum(price_unit_gara) from insurance_claim_solution_repair_line where solution_repair_id = a.id) as amount_garage
            from insurance_claim_solution_repair a
            left join insurance_claim_appraisal_detail e on a.detailed_appraisal_id = e.id
            left join res_partner_gara b on a.gara_partner_id = b.id
            left join res_partner rp on b.partner_id = rp.id
            left join insurance_claim_profile c on a.new_claim_profile_id = c.id
            left join insurance_contract_certification icc on c.certification_id = icc.id
            left join insurance_contract ic on icc.contract_id = ic.id
            left join res_car_model rcm on rcm.id = ic.car_model_id
            left join res_car_brand rcb on rcb.id = ic.car_brand_id
            left join res_users ru on a.create_uid = ru.id
            left join res_partner rpu on ru.partner_id = rpu.id
            where a.id = $1
        """
        params = [repair_id]
        results = await PostgresDB.execute_query(query, params)
        if not results or not results[0]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not Found"
            )
        res = results[0]

        query_detail = """
            select 
                repair.id as repair_id,
                line.id,
                coalesce(line.name, '') as name,
                category.name as category_name,
                category.id as category_id,
                line.price_unit_gara as garage_price,
                line.discount as discount_percentage,
                case 
                    when line.price_paint > 0 then line.price_paint 
                    when line.price_labor > 0 then line.price_labor
                    when line.price_replace > 0 then line.price_replace
                    else 0 end as suggested_price,
                case 
                    when line.price_paint > 0 then 'paint'
                    when line.price_labor > 0 then 'labor'
                    when line.price_replace > 0 then 'parts'
                    else '' end as category_type
            from insurance_claim_solution_repair_line line
            inner join insurance_claim_solution_repair repair on line.solution_repair_id = repair.id
            inner join product_product pp ON pp.id = line.product_id
            inner join product_template pt ON pt.id = pp.product_tmpl_id
            inner join insurance_claim_list_category category on line.category_id = category.id
            where repair.id = $1
            order by line.id
        """

        results_detail = await PostgresDB.execute_query(query_detail, params)
        repair_plan_details = []

        category_type_dict = {
            'paint': "Sơn",
            'labor': "Nhân công",
            'parts': "Phụ tùng",
        }

        for detail in results_detail:
            repair_plan_details.append({
                "name": detail.get('name'),
                "item": {
                    "name": detail.get('category_name'),
                    "id": detail.get('category_id'),
                },
                "type": {
                    "name": category_type_dict.get(detail.get('category_type')),
                    "code": detail.get('category_type'),
                    "color_code": CATEGORIES_COLOR.get(detail.get('category_type')),
                },
                "garage_price": int(detail.get('garage_price')),
                "suggested_price": int(detail.get('suggested_price')),
                "discount_percentage": int(detail.get('discount_percentage')),
            })

        # Mock data - replace with actual database query later
        repair_plan_detail = {
            "file_name": res.get('file_name'),
            "id": res.get('repair_id'),
            "contract_number": res.get('contract_number'),
            "vehicle_info": res.get('vehicle_info'),
            "repair_garage_location": {
                "id": res.get('gara_id'),
                "name": res.get('gara_name')
            },
            "inspection_date": res.get('inspection_date'),
            "approval_deadline": None,  # TODO chưa biết lấy ở đâu
            "owner_name": res.get('car_owner_name'),
            "owner_phone": res.get('car_owner_phone'),
            "status": {
                "name": STATE_COLOR.get(res.get('repair_state'))[1] if STATE_COLOR.get(res.get('repair_state')) else "Chờ duyệt",
                "code": res.get('repair_state'),
                "color_code": STATE_COLOR.get(res.get('repair_state'))[0] if STATE_COLOR.get(res.get('repair_state')) else "#faad14"
            },
            "btn_approve": True if res.get('repair_state') not in ('new', 'approved', 'cancel') else False,  # TODO chưa xử lý phân quyền
            "btn_reject": True if res.get('repair_state') not in ('new', 'approved', 'cancel') else False,  # TODO chưa xử lý phân quyền
            "approval_history": [],  # TODO chưa xử lý
            "repair_plan_details": repair_plan_details,
            "amount_subtotal": int(res.get('price_total_propose')),
            "amount_discount": int(res.get('total_discount')),
            "amount_untaxed_total": int(res.get('price_subtotal')),
            "amount_garage": int(res.get('amount_garage')) if res.get('amount_garage') else 0,
            "amount_propose": int(res.get('price_total_propose')),
            "label": {
                "name": "Gấp",  # TODO chưa biết lấy dữ liệu ở đâu
                "code": "LABEL001",
                "color_code": "#f5222d"
            }
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
        response = await odoo.call_method_post(
            record_id=request.repair_id,
            model='insurance.claim.solution.repair',
            method='action_approve_pass_workflow',
            token=current_user.get('token'),
            kwargs={'reason': request.approve_reason}
        )
        return RepairPlanApproveResponse(id=response)
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
        response = await odoo.call_method_post(
            record_id=request.repair_id,
            model='insurance.claim.solution.repair',
            method='action_reject_api',
            token=current_user.get('token'),
            kwargs={'reason': request.reject_reason}
        )
        if response:
            return RepairPlanRejectResponse(id=request.repair_id)
        else:
            raise Exception(response.get("message"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/repair-categories",
            response_model=List[RepairCategory],
            status_code=status.HTTP_200_OK)
async def get_repair_categories(
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> List[RepairCategory]:
    """
    Get repair categories: parts, paint, and labor
    """
    try:
        # Validate user authentication
        if not current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )

        # Return the three repair categories
        categories = [
            RepairCategory(
                code="parts",
                name="Phụ tùng",
                color_code=CATEGORIES_COLOR.get('parts')
            ),
            RepairCategory(
                code="paint",
                name="Sơn",
                color_code=CATEGORIES_COLOR.get('paint')
            ),
            RepairCategory(
                code="labor",
                name="Nhân công",
                color_code=CATEGORIES_COLOR.get('labor')
            )
        ]

        return categories

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )