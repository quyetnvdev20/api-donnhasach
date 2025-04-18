from fastapi import APIRouter, Depends, HTTPException, status, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ...deps import get_current_user
from ....config import settings, odoo
from ....database import get_db
from ....schemas.repair import RepairPlanApprovalRequest, RepairPlanApprovalResponse, RepairPlanListResponse, \
    RepairPlanDetailResponse, RepairPlanApproveRequest, RepairPlanApproveResponse, RepairPlanRejectRequest, \
    RepairPlanRejectResponse, RepairCategory, RejectionReason
import logging
import asyncio
import json
from ....utils.erp_db import PostgresDB

logger = logging.getLogger(__name__)

router = APIRouter()

STATE_COLOR = {
    "new": ("#84d9d8", "Mới"),
    "pending": ("#faad14", "Chờ duyệt"),
    "approved": ("#52c41a", "Đã duyệt"),
    "rejected": ("#f5222d", "Trả lại")
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
    response = await odoo.call_method_post(
        record_id=repair_id,
        model='insurance.claim.solution.repair',
        method='submit_repair_plan_approval',
        token=current_user.odoo_token,
        kwargs=repair_plan.model_dump()
    )
    if response.get("status_code") == status.HTTP_200_OK:
        return {'id': response.get("data")}
    else:
        raise Exception(response.get("message"))


@router.put("/{repair_id}/write-and-approve-repair-plan",
            response_model=RepairPlanApprovalResponse,
            status_code=status.HTTP_200_OK)
async def write_and_approve_repair_plan(
        repair_id: int,
        repair_plan: RepairPlanApprovalRequest,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> dict[str, int]:
    response = await odoo.call_method_post(
        record_id=repair_id,
        model='insurance.claim.solution.repair',
        method='action_write_and_approve_repair_plan',
        token=current_user.odoo_token,
        kwargs=repair_plan.model_dump()
    )
    if response.get("status_code") == status.HTTP_200_OK:
        return {'id': response.get("data")}
    else:
        raise Exception(response.get("message"))


@router.get("/repair-plan-awaiting-list",
            response_model=RepairPlanListResponse,
            status_code=status.HTTP_200_OK)
async def get_repair_plan_awaiting_list(
        state: str = 'all',
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 10,
        db: Session = Depends(get_db),
        current_user: dict = Depends(get_current_user)
) -> RepairPlanListResponse:
    """
    Get list of repair plans awaiting approval filtered by states
    Possible states: comma-separated string of 'to_do', 'waiting_approval', 'approved', 'rejected', 'all'
    Example: 'to_do,approved' will return records with state 'new' OR 'approved'
    """
    # Parse comma-separated state string into a list
    state_list = [s.strip() for s in state.split(',') if s.strip()]
    
    query = """
        with reason_table as (
            SELECT T.solution_repair_approved_id as repair_id, T.reason
            FROM (
                SELECT 
                    ROW_NUMBER() OVER (partition BY log.solution_repair_approved_id ORDER BY log.ID desc) AS RowNumber,
                    log.solution_repair_approved_id,
                    log.reason
                 FROM insurance_claim_history_log log
                 inner join insurance_claim_solution_repair repair on log.solution_repair_approved_id = repair.id
                 where log.state = 'cancel' and repair.state = 'rejected'
             ) AS T
            WHERE T.RowNumber = 1
        )
        select 
            a.id repair_id,
            a.state repair_state,
            to_char(e.date + INTERVAL '7 hours', 'dd/MM/yyyy HH24:MI') as inspection_date,
            a.price_subtotal,
            b.id as gara_id,
            rp.name gara_name,
            c.location_damage,
            a.name file_name,
            concat(rcb.name, ' ', rcm.name, ' ', ic.manufacturer_year, ' - ', ic.license_plate) as vehicle_info,
            rpu.name as submitter,
            ic.car_owner_name,
            reason_table.reason as reason_reject
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
        left join reason_table on a.id = reason_table.repair_id
        left join res_car rc ON rc.id = e.car_id
        where 1 = 1
    """

    params = {}
    state_conditions = []

    # If 'all' is in the list, we don't need to filter by state
    if 'all' not in state_list:
        if 'to_do' in state_list:
            state_conditions.append(f"a.state = %(status)s")
            params["status"] = 'new'
            
        if 'rejected' in state_list:
            state_conditions.append(f"a.state = %(status)s")
            params["status"] = 'rejected'

        if 'to_do' not in state_list and 'rejected' not in state_list:
            query += " AND (a.state IN ('new', 'rejected'))"
        
        if state_conditions:
            query += " AND (" + " OR ".join(state_conditions) + ")"
    else:
        query += " AND (a.state IN ('new', 'rejected'))"

    if search:
        query += f""" AND (
                        a.name ILIKE %(search)s
                        OR c.name ILIKE %(search)s
                        OR d.name ILIKE %(search)s
                        OR a.object_name ILIKE %(search)s
                        OR rc.license_plate ILIKE %(search)s
                        OR e.vin ILIKE %(search)s
                        OR e.engine_number ILIKE %(search)s
                        OR e.name_driver ILIKE %(search)s
        )"""

        params["search"] = f"%{search}%"

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
                "name": STATE_COLOR.get(res.get('repair_state'))[1] if STATE_COLOR.get(
                    res.get('repair_state')) else "Chờ duyệt",
                "code": res.get('repair_state'),
                "color_code": STATE_COLOR.get(res.get('repair_state'))[0] if STATE_COLOR.get(
                    res.get('repair_state')) else "#faad14"
            },
            "label": {
                "name": None,  # TODO chưa biết lấy dữ liệu ở đâu
                "code": "LABEL001",
                "color_code": None
            },
            'reason_reject': res.get('reason_reject')
        })

    return RepairPlanListResponse(
        data=formatted_plans
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
    query = """
        select 
            a.id repair_id,
            a.name as repair_name,
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
            (select sum(price_unit_gara) from insurance_claim_solution_repair_line where solution_repair_id = a.id) as amount_garage,
            c.insur_claim_id as insur_claim_id,
            (select 
                    json_agg(
                        json_build_object(
                        'id', log.id,
                        'reason', log.reason,
                        'rejection_date', to_char(log.date + INTERVAL '7 hours', 'dd/MM/yyyy HH24:MI')
                    )
                ) as rejection_reasons
                from insurance_claim_history_log log
                where log.solution_repair_approved_id = a.id
                and log.state = 'cancel') as rejection_reasons
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

    results, repair_plan_details = await asyncio.gather(
        PostgresDB.execute_query(query, params),
        get_repair_plan_line(params),
    )

    if not results or not results[0]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found"
        )
    res = results[0]

    rejection_reasons = res.get('rejection_reasons')
    list_rejection_reason = []

    if rejection_reasons and rejection_reasons != '[null]':
        # Nếu rejection_reasons đã là list, sử dụng trực tiếp
        if isinstance(rejection_reasons, list):
            list_rejection_reason = rejection_reasons
        # Nếu rejection_reasons là string JSON, parse nó
        elif isinstance(rejection_reasons, str):
            list_rejection_reason = json.loads(rejection_reasons)

    # Mock data - replace with actual database query later
    repair_plan_detail = {
        "file_name": res.get('file_name'),
        "repair_name": res.get('repair_name'),
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
            "name": STATE_COLOR.get(res.get('repair_state'))[1] if STATE_COLOR.get(
                res.get('repair_state')) else "Chờ duyệt",
            "code": res.get('repair_state'),
            "color_code": STATE_COLOR.get(res.get('repair_state'))[0] if STATE_COLOR.get(
                res.get('repair_state')) else "#faad14"
        },
        "rejection_reasons": list_rejection_reason,
        "btn_rejection": True if list_rejection_reason and res.get('repair_state') == 'rejected' else False,
        "btn_approve": True if res.get('repair_state') not in ('new', 'approved', 'cancel') else False,
        # TODO chưa xử lý phân quyền
        "btn_reject": True if res.get('repair_state') not in ('new', 'approved', 'cancel') else False,
        # TODO chưa xử lý phân quyền
        "approval_history": [],  # TODO chưa xử lý
        "repair_plan_details": repair_plan_details,
        "amount_subtotal": int(res.get('price_total_propose')),
        "amount_discount": int(res.get('total_discount')),
        "amount_untaxed_total": int(res.get('price_subtotal')),
        "amount_garage": int(res.get('amount_garage')) if res.get('amount_garage') else 0,
        "amount_propose": int(res.get('price_total_propose')),
        "label": {
            "name": None,  # TODO chưa biết lấy dữ liệu ở đâu
            "code": "LABEL001",
            "color_code": "#f5222d"
        },
        "insur_claim_id": int(res.get('insur_claim_id')) if res.get('insur_claim_id') else None
    }

    return RepairPlanDetailResponse(
        data=repair_plan_detail
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
    response = await odoo.call_method_post(
        record_id=request.repair_id,
        model='insurance.claim.solution.repair',
        method='action_approve_pass_workflow',
        token=current_user.odoo_token,
        kwargs={'reason': request.approve_reason}
    )
    return RepairPlanApproveResponse(id=response)


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
    response = await odoo.call_method_post(
        record_id=request.repair_id,
        model='insurance.claim.solution.repair',
        method='action_reject_api',
        token=current_user.odoo_token,
        kwargs={'reason': request.reject_reason}
    )
    if response:
        return RepairPlanRejectResponse(id=request.repair_id)
    else:
        raise Exception(response.get("message"))


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


async def get_repair_plan_line(params: list) -> List[Dict[str, Any]]:
    """
    Check if assessment has assessment report documents.

    Args:
        params: params

    Returns:
        Dictionary with status information
    """
    query_detail = """
        select 
            repair.id as repair_id,
            line.id,
            coalesce(line.name, '') as name,
            category.name as category_name,
            category.id as category_id,
            category.code as category_code,
            line.price_unit_gara as garage_price,
            line.discount as discount_percentage,
            line.depreciation_percentage as depreciation_percentage,
            line.incident_no as incident_no,
            line.solution as solution,
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
            "id": detail.get('id'),
            "item": {
                "name": detail.get('category_name'),
                "id": detail.get('category_id'),
                "code": detail.get('category_code'),
            },
            "type": {
                "name": category_type_dict.get(detail.get('category_type')),
                "code": detail.get('category_type'),
                "color_code": CATEGORIES_COLOR.get(detail.get('category_type')),
            },
            "garage_price": int(detail.get('garage_price')),
            "suggested_price": int(detail.get('suggested_price')),
            "discount_percentage": int(detail.get('discount_percentage')),
            "depreciation_percentage": detail.get('depreciation_percentage') if detail.get('depreciation_percentage') else 0,
            "incident_no": detail.get('incident_no'),
            "solution": detail.get('solution')
        })
    return repair_plan_details


@router.post("/{assessment_id}/create-repair")
async def create_repair(
        assessment_id: int,
        current_user: dict = Depends(get_current_user)
):
    """
    Create repair
    """


    # Tạo phương án sửa chữa
    response = await odoo.call_method_post(
        model='insurance.claim.appraisal.detail',
        record_id=assessment_id,
        method='create_repair',
        token=current_user.odoo_token,
        kwargs={}
    )

    return {
        "id": int(response.get('repair_plan_id')),
        "status": "Success"
    }
