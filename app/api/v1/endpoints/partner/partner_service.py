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
        response = await PostgresDB.execute_query(query)
        data = {}
        if response:
            response  = response[0]
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