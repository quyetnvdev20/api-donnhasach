import logging
from typing import List, Optional, Dict, Any
from app.config import settings, odoo
logger = logging.getLogger(__name__)


class PriceListSerivce:


    @staticmethod
    async def get_pricelist() -> List[Dict[str, Any]]:
        result = await odoo.call_method_not_record(
            model='product.template',
            method='get_price_pricelist',
            token=settings.ODOO_TOKEN,
            kwargs={},
        )
        return result
