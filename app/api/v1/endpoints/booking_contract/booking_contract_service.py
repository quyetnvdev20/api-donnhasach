import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class BookingContractService:

    @classmethod
    async def get_booking_contracts(
        cls,
        current_user: UserObject,
        page: int = 1,
        limit: int = 10,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lấy danh sách hợp đồng định kỳ"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='get_booking_contracts_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'partner_id': current_user.partner_id,
                    'page': page,
                    'limit': limit,
                    'from_date': from_date.strftime('%Y-%m-%d') if from_date else None,
                    'to_date': to_date.strftime('%Y-%m-%d') if to_date else None,
                    'state': state,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error getting booking contracts: {str(e)}")
            raise

    @classmethod
    async def get_booking_contract_detail(
        cls,
        contract_id: int,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Lấy chi tiết hợp đồng định kỳ - Query trực tiếp từ database"""
        try:
            # Query thông tin contract chính
            contract_query = '''
                SELECT 
                    bc.id,
                    bc.code,
                    bc.name,
                    bc.partner_id,
                    rp.name as partner_name,
                    bc.contact_id,
                    ca.name as contact_name,
                    COALESCE(
                        CONCAT_WS(', ', ca.street, rcw.name, rcs.name),
                        ''
                    ) as contact_address,
                    bc.package_id,
                    pp.name as package_name,
                    pp.duration_months as package_duration_months,
                    bc.categ_id,
                    CASE 
                        WHEN pg_typeof(pc.name) = 'jsonb'::regtype 
                        THEN COALESCE(pc.name::jsonb ->> 'vi_VN', pc.name::jsonb ->> 'en_US')
                        ELSE pc.name::text
                    END as categ_name,
                    TO_CHAR(bc.start_date, 'YYYY-MM-DD') as start_date,
                    TO_CHAR(bc.end_date, 'YYYY-MM-DD') as end_date,
                    bc.start_hours,
                    bc.appointment_duration,
                    bc.total_hours,
                    bc.required_staff_qty,
                    bc.state,
                    bc.payment_status,
                    bc.price_unit,
                    bc.base_price,
                    bc.extra_total,
                    bc.amount_before_discount,
                    bc.discount_amount,
                    bc.discount_percent,
                    bc.amount_subtotal,
                    bc.amount_tax,
                    bc.amount_total,
                    bc.program_id,
                    lp.name as program_name,
                    bc.description,
                    bc.payment_method_id,
                    pm.id as pm_id,
                    pm.name as payment_method_name,
                    pm.code as payment_method_code
                FROM booking_contract bc
                LEFT JOIN res_partner rp ON bc.partner_id = rp.id
                LEFT JOIN customer_address ca ON bc.contact_id = ca.id
                LEFT JOIN res_country_ward rcw ON ca.ward_id = rcw.id
                LEFT JOIN res_country_state rcs ON ca.state_id = rcs.id
                LEFT JOIN periodic_package pp ON bc.package_id = pp.id
                LEFT JOIN product_category pc ON bc.categ_id = pc.id
                LEFT JOIN loyalty_program lp ON bc.program_id = lp.id
                LEFT JOIN payment_method pm ON bc.payment_method_id = pm.id
                WHERE bc.id = {} AND bc.partner_id = {}
            '''.format(contract_id, current_user.partner_id)
            
            contract_result = await PostgresDB.execute_query(contract_query)
            
            if not contract_result:
                return {
                    'success': False,
                    'error': 'Không tìm thấy hợp đồng hoặc bạn không có quyền truy cập',
                    'data': None
                }
            
            contract = contract_result[0]
            
            # Query schedules
            schedules_query = '''
                SELECT 
                    sbc.id,
                    TO_CHAR(sbc.date_cleaning, 'YYYY-MM-DD') as date_cleaning,
                    sbc.time_cleaning,
                    sbc.hours,
                    sbc.base_amount,
                    sbc.amount,
                    sbc.state,
                    sbc.actual_event_id,
                    ce.id as event_id,
                    ce.name as event_name,
                    TO_CHAR(ce.start, 'YYYY-MM-DD HH24:MI:SS') as event_start,
                    ce.cleaning_state
                FROM schedule_booking_calendar sbc
                LEFT JOIN calendar_event ce ON sbc.actual_event_id = ce.id
                WHERE sbc.contract_id = {}
                ORDER BY sbc.date_cleaning ASC
            '''.format(contract_id)
            
            schedules_result = await PostgresDB.execute_query(schedules_query)
            
            schedules = []
            for schedule in schedules_result:
                schedule_data = {
                    'id': schedule.get('id'),
                    'date_cleaning': schedule.get('date_cleaning'),
                    'time_cleaning': schedule.get('time_cleaning'),
                    'hours': schedule.get('hours'),
                    'base_amount': schedule.get('base_amount'),
                    'amount': schedule.get('amount'),
                    'state': schedule.get('state'),
                    'actual_event_id': schedule.get('actual_event_id'),
                }
                
                # Thêm actual_event nếu có
                if schedule.get('event_id'):
                    schedule_data['actual_event'] = {
                        'id': schedule.get('event_id'),
                        'name': schedule.get('event_name'),
                        'start': schedule.get('event_start'),
                        'cleaning_state': schedule.get('cleaning_state'),
                    }
                else:
                    schedule_data['actual_event'] = None
                
                schedules.append(schedule_data)
            
            # Query extra services
            extra_services_query = '''
                SELECT 
                    es.id,
                    es.product_id,
                    CASE 
                        WHEN pg_typeof(pt.name) = 'jsonb'::regtype 
                        THEN COALESCE(pt.name::jsonb ->> 'vi_VN', pt.name::jsonb ->> 'en_US')
                        ELSE pt.name::text
                    END as product_name,
                    es.quantity,
                    es.price_unit
                FROM extra_service es
                LEFT JOIN product_product pp ON es.product_id = pp.id
                LEFT JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE es.contract_id = {}
            '''.format(contract_id)
            
            extra_services_result = await PostgresDB.execute_query(extra_services_query)
            
            extra_services = []
            for extra in extra_services_result:
                extra_services.append({
                    'id': extra.get('id'),
                    'product_id': extra.get('product_id'),
                    'product_name': extra.get('product_name'),
                    'quantity': extra.get('quantity'),
                    'price_unit': extra.get('price_unit'),
                })
            
            # Payment method
            payment_method = None
            if contract.get('pm_id'):
                payment_method = {
                    'id': contract.get('pm_id'),
                    'name': contract.get('payment_method_name'),
                    'code': contract.get('payment_method_code'),
                }
            
            # Build response
            data = {
                'id': contract.get('id'),
                'code': contract.get('code'),
                'name': contract.get('name'),
                'partner_id': contract.get('partner_id'),
                'partner_name': contract.get('partner_name'),
                'contact_id': contract.get('contact_id'),
                'contact_name': contract.get('contact_name'),
                'contact_address': contract.get('contact_address') or '',
                'package_id': contract.get('package_id'),
                'package_name': contract.get('package_name') or '',
                'package_duration_months': contract.get('package_duration_months') or 0,
                'categ_id': contract.get('categ_id'),
                'categ_name': contract.get('categ_name') or '',
                'start_date': contract.get('start_date'),
                'end_date': contract.get('end_date'),
                'start_hours': contract.get('start_hours'),
                'appointment_duration': contract.get('appointment_duration'),
                'total_hours': contract.get('total_hours'),
                'required_staff_qty': contract.get('required_staff_qty'),
                'state': contract.get('state'),
                'payment_status': contract.get('payment_status'),
                'payment_method': payment_method,
                'price_unit': contract.get('price_unit'),
                'base_price': contract.get('base_price'),
                'extra_total': contract.get('extra_total'),
                'amount_before_discount': contract.get('amount_before_discount'),
                'discount_amount': contract.get('discount_amount'),
                'discount_percent': contract.get('discount_percent'),
                'amount_subtotal': contract.get('amount_subtotal'),
                'amount_tax': contract.get('amount_tax'),
                'amount_total': contract.get('amount_total'),
                'program_id': contract.get('program_id'),
                'program_name': contract.get('program_name') or '',
                'description': contract.get('description') or '',
                'schedules': schedules,
                'extra_services': extra_services,
                'is_periodic': True,
            }
            
            return {
                'success': True,
                'data': data
            }
        except Exception as e:
            logger.error(f"Error getting booking contract detail: {str(e)}")
            return {
                'success': False,
                'error': f'Lỗi khi lấy chi tiết hợp đồng: {str(e)}',
                'data': None
            }

    @classmethod
    async def check_schedule_price(
        cls,
        contract_id: int,
        schedule_id: int,
        new_date: str,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Kiểm tra giá khi đổi lịch"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='check_schedule_price_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'schedule_id': schedule_id,
                    'new_date': new_date,
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error checking schedule price: {str(e)}")
            raise

    @classmethod
    async def update_schedule_date(
        cls,
        contract_id: int,
        schedule_id: int,
        data: dict,
        current_user: UserObject,
    ) -> Dict[str, Any]:
        """Đổi lịch schedule.booking.calendar"""
        try:
            result = await odoo.call_method_not_record(
                model='booking.contract',
                method='update_schedule_date_api',
                token=settings.ODOO_TOKEN,
                kwargs={
                    'contract_id': contract_id,
                    'schedule_id': schedule_id,
                    'new_date': data.get('new_date'),
                    'partner_id': current_user.partner_id,
                },
            )
            return result
        except Exception as e:
            logger.error(f"Error updating schedule date: {str(e)}")
            raise

    @classmethod
    async def create_booking_contract(cls, data: dict, current_user: UserObject):
        """Tạo hợp đồng dọn dẹp định kỳ"""
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='booking.contract',
            method='create_periodic_booking_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result
    

