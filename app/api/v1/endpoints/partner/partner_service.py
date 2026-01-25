import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo

logger = logging.getLogger(__name__)


class PartnerService:

    @classmethod
    async def get_current_partner(cls, current_user: UserObject):

        query = '''
            SELECT 
                ru.id,
                rp.name,
                ru.login,
                rp.id AS partner_id,
                (
                    COALESCE(rp.street, '') 
                    || CASE WHEN rcw.name IS NOT NULL THEN ', ' || rcw.name ELSE '' END
                    || CASE WHEN rcs.name IS NOT NULL THEN ', ' || rcs.name ELSE '' END
                ) AS full_address,
                TO_CHAR(rp.create_date + interval '7 hours', 'HH24:MI DD-MM-YYYY') AS create_date,
                COUNT(ce.id) AS total_calendar_event
            FROM res_users ru
            LEFT JOIN res_partner rp ON ru.partner_id = rp.id
            LEFT JOIN res_country_ward rcw ON rp.ward_id = rcw.id
            LEFT JOIN res_country_state rcs ON rp.state_id = rcs.id
            LEFT JOIN calendar_event ce ON ce.partner_id = rp.id
            where ru.id = {}
            GROUP BY
                ru.id,
                rp.name,
                ru.login,
                rp.id,
                rp.street,
                rcw.name,
                rcs.name,
                rp.create_date;
            '''.format(int(current_user.uid))
        response = await PostgresDB.execute_query(query)
        data = {}
        if response:
            response = response[0]
            data = {
                'id': response.get('id'),
                'name': response.get('name'),
                'address': response.get('full_address'),
                'login': response.get('login'),
                'partner_id': response.get('partner_id'),
                'create_date': response.get('create_date'),
                'total_calendar_event': response.get('total_calendar_event'),
            }

        result = {
            'success': True,
            'data': data
        }

        return result

    @classmethod
    async def get_add_partner(cls, current_user: UserObject):

        query = '''
        SELECT 
        ca.id as contact_id,
        ca.name as contact_name,
        rcw.id as ward_id,
        rcs.id as state_id,
        rcw.name as ward_name,
        rcs.name as state_name,
        ca.is_default as is_default,
        ca.street as street,
        CONCAT_WS(', ', ca.street, rcw.name, rcs.name) AS contact_address,
        ca.phone as phone
        from customer_address ca
        LEFT JOIN res_country_ward rcw ON ca.ward_id = rcw.id
        LEFT JOIN res_country_state rcs ON ca.state_id = rcs.id
        where ca.partner_id = {}
        ORDER BY ca.is_default DESC, ca.id DESC
        '''.format(int(current_user.partner_id))
        responses = await PostgresDB.execute_query(query)
        data = []
        if responses:
            for response in responses:
                data.append({
                    'id': response.get('contact_id'),
                    'name': response.get('contact_name'),
                    'address': response.get('contact_address'),
                    'is_default': response.get('is_default'),
                    'street': response.get('street'),
                    'ward': {
                        'id': response.get('ward_id'),
                        'name': response.get('ward_name'),
                    },
                    'state': {
                        'id': response.get('state_id'),
                        'name': response.get('state_name'),
                    },
                    'phone': response.get('phone'),

                })

        result = {
            'success': True,
            'data': data
        }

        return result


    @classmethod
    async def create_contact_partner(cls, data: dict, current_user: UserObject):
        data.update({
            'partner_id': current_user.partner_id
        })
        result = await odoo.call_method_not_record(
            model='res.partner',
            method='create_contract_partner_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

    @classmethod
    async def update_contact_partner(cls, data: dict, contact_id: int, current_user: UserObject):
        data.update({
            'partner_id': current_user.partner_id,
            'id': contact_id
        })
        result = await odoo.call_method_not_record(
            model='res.partner',
            method='update_contract_partner_api',
            token=settings.ODOO_TOKEN,
            kwargs=data,
        )
        return result

