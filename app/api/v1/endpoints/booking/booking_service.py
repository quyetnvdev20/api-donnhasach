import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo
from datetime import datetime
from app.api.deps import get_value_fields_selection
import locale

logger = logging.getLogger(__name__)


class BookingService:

    @staticmethod
    async def get_booking(
            current_user: UserObject,
            page: int = 1,
            limit: int = 10,
            from_date: Optional[datetime] = None,
            to_date: Optional[datetime] = None,
            cleaning_state: str = None,
    ) -> Dict[str, Any]:
        try:
            # Tính offset
            offset = (page - 1) * limit

            # Build query điều kiện
            where_clause = "1=1"

            where_clause += " and ce.partner_id = {} ".format(int(current_user.partner_id))




            if from_date and to_date:
                where_clause += " and ce.start between '{}' and '{}' ".format(from_date, to_date)

            if cleaning_state:
                where_clause += " and ce.cleaning_state = '{}' ".format(cleaning_state)

            query = '''
                    SELECT
                        ce.id,
                        ce.cleaning_state,
                        ce.amount_subtotal,
                        ce.amount_tax,
                        ce.amount_total,
                        pp.id as product_id,
                        
                        COALESCE(pt.name ->> 'vi_VN', pt.name ->> 'en_US') AS product_name,
                        STRING_AGG(
                            CASE
                                WHEN he.birthday IS NOT NULL THEN he.name || ' (' || EXTRACT(YEAR FROM he.birthday)::text || ')'
                                ELSE he.name
                            END,
                            ', ' ORDER BY he.name
                        ) AS employees,
                        TO_CHAR(ce.start + interval '7 hours', 'DD-MM-YYYY HH24:MI') as start,
                        TO_CHAR(ce.stop + interval '7 hours', 'DD-MM-YYYY HH24:MI') as stop,
                        ce.description as description,
                        rc.phone as company_phone,
                        rpc.id as contact_id,
                        rcw2.id as contact_ward_id,
                        rcs2.id as contact_state_id,
                        rpc.phone as contact_phone,
                        rpc.name as contact_name,
                        CONCAT_WS(', ', rpc.street, rcw2.name, rcs2.name) AS contact_address,
                        coalesce((select rp.phone from res_company rc join res_partner rp on rc.partner_id = rp.id limit 1), '') as company_phone,
                        ce.estimated_total
                    FROM calendar_event ce
                         JOIN product_product pp ON ce.service_product_id = pp.id
                         JOIN product_template pt ON pp.product_tmpl_id = pt.id
                         left join calendar_event_staff_rel cesr ON ce.id = cesr.event_id
                         left join  hr_employee he ON cesr.employee_id = he.id
                         left join res_country_ward rcw on ce.ward_id = rcw.id
                         left join res_country_state rcs on rcs.id = ce.state_id
                         left join res_company rc on ce.company_id = ce.id
                         left join res_partner rpc on ce.contact_id = rpc.id
                         left join res_country_ward rcw2 on rpc.ward_id = rcw2.id
                         left join res_country_state rcs2 on rcs2.id = rpc.state_id 
                    where  {}
                    GROUP BY ce.id, ce.cleaning_state, ce.amount_subtotal, pt.name, rcw.name, rcs.name, rc.phone, 
                    pp.id, rpc.id, rcw2.id, rcs2.id, rpc.phone, rpc.name, rpc.street, rcw2.name, rcs2.name,ce.estimated_total
                    LIMIT {} OFFSET {}
                '''.format(where_clause, limit, offset)

            # Query đếm tổng số bài viết
            count_query = '''
                    SELECT COUNT(ce.id) as total
                    FROM calendar_event ce
                         JOIN product_product pp ON ce.service_product_id = pp.id
                         JOIN product_template pt ON pp.product_tmpl_id = pt.id
                         left join calendar_event_staff_rel cesr ON ce.id = cesr.event_id
                         left join  hr_employee he ON cesr.employee_id = he.id
                         left join res_country_ward rcw on ce.ward_id = rcw.id
                         left join res_country_state rcs on rcs.id = ce.state_id
                         left join res_company rc on ce.company_id = ce.id
                         left join res_partner rpc on ce.contact_id = rpc.id
                         left join res_country_ward rcw2 on rpc.ward_id = rcw2.id
                         left join res_country_state rcs2 on rcs2.id = rpc.state_id 
                    where {}
                    GROUP BY ce.id, ce.cleaning_state, ce.amount_subtotal, pt.name, rcw.name, rcs.name, rc.phone, 
                    pp.id, rpc.id, rcw2.id, rcs2.id, rpc.phone, rpc.name, rpc.street, rcw2.name, rcs2.name
                '''.format(where_clause)

            # Thực hiện queries
            posts_result = await PostgresDB.execute_query(query)
            data = []

            ## get select state
            leaning_state = await get_value_fields_selection('calendar.event', 'cleaning_state')

            try:
                locale.setlocale(locale.LC_TIME, 'vi_VN.UTF-8')
            except locale.Error:
                # Nếu không có locale tiếng Việt, dùng English fallback
                locale.setlocale(locale.LC_TIME, 'C')

            for item in posts_result:
                start_dt = datetime.strptime(item.get('start'), '%d-%m-%Y %H:%M')
                stop_dt = datetime.strptime(item.get('stop'), '%d-%m-%Y %H:%M')
                date_to_string = start_dt.strftime("%A, %d tháng %m, %Y").replace(" 0", " ")
                time_to_string = f"{start_dt.strftime('%H:%M')} - {stop_dt.strftime('%H:%M')}"
                vals = {

                    'id': item.get('id'),
                    'cleaning_state': {
                        'key': item.get('cleaning_state'),
                        'value': leaning_state.get(item.get('cleaning_state'), ''),
                    },
                    'amount_subtotal': item.get('amount_subtotal'),
                    'amount_tax': item.get('amount_tax'),
                    'amount_total': item.get('amount_total') if item.get('amount_total') else item.get('estimated_total'),
                    'product_service':{
                        'id': item.get('product_id'),
                        'name': item.get('product_name'),
                    },
                    'employee': item.get('employees'),
                    'date_start': item.get('start'),
                    'date_end': item.get('stop'),
                    'description': item.get('description'),
                    'company_phone': item.get('company_phone'),
                    'date_to_string': date_to_string,
                    'time_to_string': time_to_string,
                    'contact': {
                        'id': item.get('contact_id'),
                        'name': item.get('contact_name'),
                        'phone': item.get('contact_phone'),
                        'ward_id': item.get('contact_ward_id'),
                        'state_id': item.get('contact_state_id'),
                        'address': item.get('contact_address'),
                    },
                    'phone_company': item.get('phone_company'),
                }
                data.append(vals)


            count_result = await PostgresDB.execute_query(count_query)

            total = count_result[0]["total"] if count_result else 0
            total_pages = (total + limit - 1) // limit

            return {
                "success": True,
                "data": data,
                "current_page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
            }

        except Exception as e:
            logger.error(f"Error getting calendar event: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy danh sách lịch dọn dẹp: {str(e)}",
                "data": None
            }

    @staticmethod
    async def get_booking_detail(booking_id: int) -> Dict[str, Any]:
        try:
            # Query lấy chi tiết bài viết
            detail_query = '''
                SELECT
                        ce.id,
                        ce.cleaning_state,
                        ce.price_per_hour,
                        ce.amount_subtotal,
                        ce.amount_tax,
                        ce.amount_total,
                        ce.estimated_price,
                        ce.estimated_tax,
                        ce.estimated_total,
                        ce.appointment_duration,
                        pp.id as product_id,
                        
                        COALESCE(pt.name ->> 'vi_VN', pt.name ->> 'en_US') AS product_name,
                        STRING_AGG(
                            CASE
                                WHEN he.birthday IS NOT NULL THEN he.name || ' (' || EXTRACT(YEAR FROM he.birthday)::text || ')'
                                ELSE he.name
                            END,
                            ', ' ORDER BY he.name
                        ) AS employees,
                        TO_CHAR(ce.start + interval '7 hours', 'DD-MM-YYYY HH24:MI') as start,
                        TO_CHAR(ce.stop + interval '7 hours', 'DD-MM-YYYY HH24:MI') as stop,
                        CONCAT_WS(', ', ce.street, rcw.name, rcs.name) AS address,
                        ce.description as description,
                        rpc.id as contact_id,
                        rcw2.id as contact_ward_id,
                        rcs2.id as contact_state_id,
                        rpc.phone as contact_phone,
                        rpc.name as contact_name,
                        CONCAT_WS(', ', rpc.street, rcw2.name, rcs2.name) AS contact_address,
                        coalesce((select rp.phone from res_company rc join res_partner rp on rc.partner_id = rp.id limit 1), '') as company_phone
                    FROM calendar_event ce
                         JOIN product_product pp ON ce.service_product_id = pp.id
                         JOIN product_template pt ON pp.product_tmpl_id = pt.id
                         left join calendar_event_staff_rel cesr ON ce.id = cesr.event_id
                         left join  hr_employee he ON cesr.employee_id = he.id
                         left join res_country_ward rcw on ce.ward_id = rcw.id
                         left join res_country_state rcs on rcs.id = ce.state_id
                         left join res_company rc on ce.company_id = ce.id
                         left join res_partner rpc on ce.contact_id = rpc.id
                         left join res_country_ward rcw2 on rpc.ward_id = rcw2.id
                         left join res_country_state rcs2 on rcs2.id = rpc.state_id
                    where  ce.id = {}
                    GROUP BY ce.id, ce.cleaning_state, ce.amount_subtotal, pt.name, rcw.name, rcs.name, rc.phone, 
                    pp.id, rpc.id, rcw2.id, rcs2.id, rpc.phone, rpc.name, rpc.street, rcw2.name, rcs2.name, ce.price_per_hour,ce.estimated_price, ce.estimated_tax,ce.estimated_total
            '''.format(booking_id)

            result = await PostgresDB.execute_query(detail_query)

            if not result:
                return {
                    "success": False,
                    "error": "Không tìm thấy bài viết",
                    "data": None
                }

            item = result[0]

            ## get select state
            leaning_state = await get_value_fields_selection('calendar.event', 'cleaning_state')
            try:
                locale.setlocale(locale.LC_TIME, 'vi_VN.UTF-8')
            except locale.Error:
                # Nếu không có locale tiếng Việt, dùng English fallback
                locale.setlocale(locale.LC_TIME, 'C')

            start_dt = datetime.strptime(item.get('start'), '%d-%m-%Y %H:%M')
            stop_dt = datetime.strptime(item.get('stop'), '%d-%m-%Y %H:%M')
            date_to_string = start_dt.strftime("%A, %d tháng %m, %Y").replace(" 0", " ")
            time_to_string = f"{start_dt.strftime('%H:%M')} - {stop_dt.strftime('%H:%M')}"

            data = {

                'id': item.get('id'),
                'cleaning_state': {
                    'key': item.get('cleaning_state'),
                    'value': leaning_state.get(item.get('cleaning_state'), ''),
                },
                'price_per_hour': item.get('price_per_hour'),
                'appointment_duration': item.get('appointment_duration'),
                'amount_subtotal': item.get('amount_subtotal'),
                'amount_tax': item.get('amount_tax'),
                'amount_total': item.get('amount_total'),
                'estimated_price': item.get('estimated_price'),
                'estimated_tax': item.get('estimated_tax'),
                'estimated_total': item.get('estimated_total'),
                'discount_amount': 0,
                'product_service': {
                    'id': item.get('product_id'),
                    'name': item.get('product_name'),
                },
                'employee': item.get('employees'),
                'date_start': item.get('start'),
                'date_end': item.get('stop'),
                'description': item.get('description'),
                'company_phone': item.get('company_phone'),
                'date_to_string': date_to_string,
                'time_to_string': time_to_string,
                'contact': {
                    'id': item.get('contact_id'),
                    'name': item.get('contact_name'),
                    'phone': item.get('contact_phone'),
                    'ward_id': item.get('contact_ward_id'),
                    'state_id': item.get('contact_state_id'),
                    'address': item.get('contact_address'),
                },
            }



            return {
                "success": True,
                "data": data
            }

        except Exception as e:
            logger.error(f"Error getting blog post detail: {str(e)}")
            return {
                "success": False,
                "error": f"Lỗi khi lấy chi tiết lịch hẹn: {str(e)}",
                "data": None
            }

    @classmethod
    async def get_pricing_calculate(cls, data: dict, current_user: UserObject):
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='calendar.event',
            method='get_calculate_booking',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

    @classmethod
    async def create_event(cls, data: dict, current_user: UserObject):
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='calendar.event',
            method='create_booking',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

    @classmethod
    async def get_value_state(cls):
        leaning_state = await get_value_fields_selection('calendar.event', 'cleaning_state')
        return leaning_state

    @classmethod
    async def cancel_booking(cls, data: dict):
        result = await odoo.call_method_not_record(
            model='calendar.event',
            method='cancel_event_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return {
            'id': data.get('booking_id'),
        }
