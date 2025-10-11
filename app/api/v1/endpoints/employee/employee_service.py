import logging
from typing import List, Optional, Dict, Any
from app.utils.erp_db import PostgresDB
from app.schemas.user import UserObject
from app.config import settings, odoo
logger = logging.getLogger(__name__)


class EmployeeService:

    @classmethod
    async def get_employee_available(cls, category_id : int, current_user: UserObject):
        response = await odoo.call_method_not_record(
            model='hr.employee',
            method='get_available_employee_api',
            token=settings.ODOO_TOKEN,
            kwargs={'categ_id': category_id, 'user_id': current_user.uid},
        )


        result = {
            'success': True,
            'data': response
        }

        return result