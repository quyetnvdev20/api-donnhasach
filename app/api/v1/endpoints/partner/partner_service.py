import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject

logger = logging.getLogger(__name__)


class PartnerService:

    @classmethod
    async def get_current_partner(cls, current_user: UserObject):

        query = '''
            SELECT 
                ru.id,
                rp.name,
                ru.login,
                rp.id as partner_id,
                (COALESCE(rp.street, '') 
                 || CASE WHEN rcw.name IS NOT NULL THEN ', ' || rcw.name ELSE '' END
                 || CASE WHEN rcs.name IS NOT NULL THEN ', ' || rcs.name ELSE '' END
                ) AS full_address
            FROM res_users ru
            LEFT JOIN res_partner rp ON ru.partner_id = rp.id
            LEFT JOIN res_country_ward rcw ON rp.ward_id = rcw.id
            LEFT JOIN res_country_state rcs ON rp.state_id = rcs.id
            where ru.id = {}
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
        rp.id as contact_id,
        rp.name as contact_name,
        rcw.id as ward_id,
        rcs.id as state_id,
        rcw.name as ward_name,
        rcs.name as state_name,
        rp.is_default as is_default,
        rp.street as street,
        CONCAT_WS(', ', rp.street, rcw.name, rcs.name) AS contact_address
        from res_partner rp
        LEFT JOIN res_country_ward rcw ON rp.ward_id = rcw.id
        LEFT JOIN res_country_state rcs ON rp.state_id = rcs.id
        where rp.parent_id = {}
        '''.format(int(current_user.partner_id))
        responses = await PostgresDB.execute_query(query)
        data = []
        if responses:
            for response in responses:
                data = {
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
                    }

                }

        result = {
            'success': True,
            'data': data
        }

        return result
