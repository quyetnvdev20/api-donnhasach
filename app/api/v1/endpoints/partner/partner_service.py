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
            response  = response[0]
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