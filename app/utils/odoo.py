#! -*- coding: utf-8 -*-
import logging
import os
import traceback

import requests
import httpx
import json
import asyncio
from fastapi.exceptions import RequestValidationError, HTTPException

# Tạo custom exception classes
class UnauthorizedError(HTTPException):
    def __init__(self, detail="Unauthorized"):
        super().__init__(status_code=401, detail=detail)

class ForbiddenError(HTTPException):
    def __init__(self, detail="Forbidden"):
        super().__init__(status_code=403, detail=detail)

class UserError(HTTPException):
    def __init__(self, detail="User Error", description=None):
        if description:
            detail = f"{detail}: {description}"
        super().__init__(status_code=422, detail=detail)

# TimeoutError đã có sẵn trong Python
# Sử dụng TimeoutError của Python thay vì import từ fastapi.exceptions

TIMEOUT = 3600
_logger = logging.getLogger('apis')

    

def get_debug_exception(error: Exception):
    return '\n'.join(traceback.format_tb(error.__traceback__)).strip()

# TODO: Try-catch và trả về Exception detail hơn khi connect với
# Các Exception được định nghĩa chi tiết ở blueprint Exception
# Các lỗi cơ bản: ko kết nối được backend, kết nối nhưng ko execute được ...
# Vì các hàm giống nhau nên có thể viết decorator để chạy .

class RequestOdoo():

    async def get(self, url):
        try:
            headers = {'Content-Type': 'application/json'}
            async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:
                response = await client.get(url=url, headers=headers)
                res = response.text
                _logger.info(f'RequestOdoo.get.res={res}')
                res_data = json.loads(res, strict=False)
        except httpx.TimeoutException:
            raise TimeoutError('Timeout get data')
        except httpx.RequestError as ex:
            raise HTTPException(status_code=500, detail=str(ex))
        if 'error' in res_data:
            if res_data.get('exception_type') == 'MissingError':
                raise UserError("Đối tượng không tồn tại", description=res_data.get('debug'))
            elif res_data.get('exception_type') == 'AttributeError':
                raise UserError("Thuộc tính không hợp lệ", description=res_data.get('debug'))
            elif res_data.get('exception_type') == 'AccessError':
                raise UserError("Bạn không có quyền thực hiện hành động này", description=res_data.get('debug'))
            elif res_data.get('exception_type') == 'UserError':
                raise UserError(res_data.get('error'), description=res_data.get('debug'))
            res_error = res_data['error']
            if res_error == 'Invalid User Token':
                raise UnauthorizedError("Invalid User Token")
            raise HTTPException(status_code=422, detail=res_error)
        if 'success' in res_data:
            return res_data['success']
        return res_data

    async def post(self, url, data):
        try:
            headers = {'Content-Type': 'application/json'}
            async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:
                response = await client.post(url=url, data=json.dumps(data), headers=headers)
                res = response.text
                _logger.debug(f'RequestOdoo.post.json={res}')
        except httpx.TimeoutException as ex:
            _logger.error('post.Timeout.url={}'.format(url))
            _logger.error('post.Timeout.ex={}'.format(ex))
            raise TimeoutError('Timeout execute')
        except httpx.RequestError as ex:
            _logger.error('post.RequestException.url={}'.format(url))
            _logger.error('post.RequestException.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))
        except Exception as ex:
            _logger.error('post.Exception.url={}'.format(url))
            _logger.error('post.Exception.ex={}'.format(ex))

            raise HTTPException(status_code=500, detail=str(ex))
        res = json.loads(res, strict=False)
        if 'result' in res:
            result = json.loads(res.get('result'), strict=False)
            if 'error' in result:
                res_data = result.get('error')
                if res_data == 'Invalid User Token':
                    raise UnauthorizedError("Invalid User Token")
                raise HTTPException(status_code=422, detail=res_data)
            if 'success' in result:
                res_data = result.get('success')
                return res_data
        if 'error' in res:
            error_data = res.get('error').get('data')
            exception_type = error_data.get('exception_type')
            if exception_type == 'access_error':
                _logger.error('post.access_error.message={}'.format(error_data.get('message')))
                raise UserError("Bạn không có quyền thực hiện hành động này")
            elif exception_type == 'validation_error':
                _logger.error('post.validation_error.message={}'.format(error_data.get('message')))
                raise UserError("Thông tin xác nhận không phù hợp")
            else:
                _logger.error('post.error.message={}'.format(error_data.get('message')))
                raise UserError(error_data.get('message'), description=error_data.get('debug'))
        return res


class Odoo(RequestOdoo):
    def __init__(self, app=None, config=None):
        self.config = config
        if app is not None:
            self.init_app(app, config)

    def init_app(self, app, config=None):
        if not (config is None or isinstance(config, dict)):
            raise TypeError("config must be an instance of dict or None")

        base_config = {
            'ODOO_URL': os.getenv('ODOO_URL', ''),
            'ODOO_TOKEN': os.getenv('ODOO_TOKEN', ''),
        }

        if config is not None:
            base_config.update(config)
        self.config = base_config

    async def search_method(self, model, token=None, record_id=None, fields=None, domain=[], offset=None, limit=None,
                      order=None):
        _logger.info(f"search_method.model={model}")
        if not token:
            token = self.config['ODOO_TOKEN']
        if record_id:
            url = '{0}/api/{1}/search/{2}?token={3}&fields={4}'.format(self.config['ODOO_URL'], model, record_id, token,
                                                                       fields)
        else:
            if order:
                url = '{0}/api/{1}/search?token={2}&fields={3}&domain={4}&offset={5}&limit={6}&order={7}'.format(
                    self.config['ODOO_URL'], model, token, fields, domain, offset, limit, order)
            else:
                url = '{0}/api/{1}/search?token={2}&fields={3}&domain={4}&offset={5}&limit={6}'.format(
                    self.config['ODOO_URL'], model, token, fields, domain, offset, limit)
        try:
            _logger.info('search_method.url={}'.format(url))
            async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:
                response = await client.get(url=url)
                res = response.text
                res = json.loads(res, strict=False)
        except httpx.TimeoutException as ex:
            _logger.error('search_method.Timeout.url={}'.format(url))
            _logger.error('search_method.Timeout.ex={}'.format(ex))
            raise TimeoutError('Timeout execute')
        except httpx.RequestError as ex:
            _logger.error('search_method.RequestException.url={}'.format(url))
            _logger.error('search_method.RequestException.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))
        except Exception as ex:
            _logger.error('search_method.Exception.url={}'.format(url))
            _logger.error('search_method.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

        if 'error' in res:
            res_data = str(res['error'])
            if 'Invalid User Token' in res_data:
                raise UnauthorizedError("Invalid User Token")
            raise HTTPException(status_code=500, detail=res_data)
        return res

    async def search_ids(self, model, token=None, domain=[], offset=0, limit=None, order=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        if order:
            url = '{0}/api/{1}/search_ids?token={2}&domain={3}&offset={4}&limit={5}&order={6}'.format(
                self.config['ODOO_URL'], model, token, domain, offset, limit, order)
        else:
            url = '{0}/api/{1}/search_ids?token={2}&domain={3}&offset={4}&limit={5}'.format(
                self.config['ODOO_URL'], model, token, domain, offset, limit)
        try:
            _logger.info('search_ids.url={}'.format(url))
            async with httpx.AsyncClient(timeout=TIMEOUT, verify=True) as client:
                response = await client.get(url=url)
                res = response.text
                res = json.loads(res, strict=False)
        except httpx.TimeoutException as ex:
            _logger.error('search_ids.Timeout.url={}'.format(url))
            _logger.error('search_ids.Timeout.ex={}'.format(ex))
            raise TimeoutError('Timeout execute')
        except httpx.RequestError as ex:
            _logger.error('search_ids.RequestException.url={}'.format(url))
            _logger.error('search_ids.RequestException.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))
        except Exception as ex:
            _logger.error('search_ids.Exception.url={}'.format(url))
            _logger.error('search_ids.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

        if 'error' in res:
            res_data = str(res['error'])
            if 'Invalid User Token' in res_data:
                raise UnauthorizedError("Invalid User Token")
            raise HTTPException(status_code=500, detail=res_data)
        return res

    async def create_method(self, model, vals, token=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        url = '{0}/api/{1}/create?token={2}'.format(self.config['ODOO_URL'], model, token)
        try:
            _logger.info('create_method.url={}'.format(url))
            _logger.info('create_method.vals={}'.format(vals))
            return await self.post(url, vals)
        except Exception as ex:
            _logger.error('create_method.Exception.url={}'.format(url))
            _logger.error('create_method.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

    async def update_method(self, model, record_id, vals, token=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        url = '{0}/api/{1}/update/{2}?token={3}'.format(self.config['ODOO_URL'], model, record_id, token)
        try:
            _logger.info('update_method.url={}'.format(url))
            _logger.info('update_method.vals={}'.format(vals))
            return await self.post(url, vals)
        except Exception as ex:
            _logger.error('update_method.Exception.url={}'.format(url))
            _logger.error('update_method.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

    async def delete_method(self, model, record_id, token):
        url = '{0}/api/{1}/unlink/{2}?token={3}'.format(self.config['ODOO_URL'], model, record_id, token)
        _logger.info('delete_method.url={}'.format(url))
        return await self.post(url, {})

    async def call_method(self, model, record_ids, method, token=None, fields=None, kwargs=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        if not kwargs:
            kwargs = {}
        if len(record_ids) == 1:
            url = '{0}/api/{1}/{2}/method/{3}?token={4}&kwargs={5}'.format(self.config['ODOO_URL'], model, record_ids[0], method, token, kwargs)
        else:
            url = '{0}/api/{1}/method/{2}?token={3}&kwargs={4}'.format(self.config['ODOO_URL'], model, method, token, kwargs)
        if fields:
            url = '{0}&fields={1}'.format(url, fields)
        try:
            _logger.info('call_method.url={}'.format(url))
            _logger.info('call_method.kwargs={}'.format(kwargs))
            return await self.get(url)
        except Exception as ex:
            _logger.error('call_method.Exception.url={}'.format(url))
            _logger.error('call_method.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

    async def call_method_post(self, model, record_id, method, token=None, fields=None, kwargs=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        data = {'params': {'kwargs': kwargs, 'token': token}}
        url = '{0}/api/{1}/{2}/method_post/{3}'.format(self.config['ODOO_URL'], model, record_id,
                                                  method)
        # url = '{0}/api/{1}/method_post/{2}/{3}?token={4}'.format(self.config['ODOO_URL'], model, record_id, method, token)

        _logger.info('call_method_post.url={}'.format(url))
        _logger.info('call_method_post.kwargs={}'.format(kwargs))
        return await self.post(url=url, data=data)

    async def authenticate(self, login, password):
        url = '{0}/api/authenticate?login={1}&password={2}'.format(self.config['ODOO_URL'], login, password)
        return await self.get(url)

    async def reset_password(self, login, password):
        url = '{0}/api/reset_password?login={1}&password={2}'.format(self.config['ODOO_URL'], login, password)
        return await self.get(url)

    async def call_method_not_record(self, model, method, token=None, fields=None, kwargs=None, base_url=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        if not kwargs:
            kwargs = {}
        if not base_url:
            base_url = self.config['ODOO_URL']
        data = {'params': {'kwargs': kwargs, 'token': token}}
        url = '{0}/api/{1}/method_not_record/{2}?token={3}'.format(base_url, model, method, token)
        if fields:
            url = '{0}&fields={1}'.format(url, fields)
        try:
            _logger.info('call_method_not_record.url={}'.format(url))
            _logger.info('call_method_not_record.kwargs={}'.format(kwargs))
            return await self.post(url, data)
        except Exception as ex:
            _logger.error('call_method_not_record.Exception.url={}'.format(url))
            _logger.error('call_method_not_record.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))

    async def call_method_record(self, model, method, token=None, fields=None, kwargs=None):
        if not token:
            token = self.config['ODOO_TOKEN']
        if not kwargs:
            kwargs = {}
        url = '{0}/api/{1}/call_record/{2}?token={3}'.format(self.config['ODOO_URL'], model, method, token)
        if fields:
            url = '{0}&fields={1}'.format(url, fields)
        try:
            _logger.info('call_method_record.url={}'.format(url))
            _logger.info('call_method_record.kwargs={}'.format(kwargs))
            return await self.post(url, kwargs)
        except Exception as ex:
            _logger.error('call_method_record.Exception.url={}'.format(url))
            _logger.error('call_method_record.Exception.ex={}'.format(ex))
            raise HTTPException(status_code=500, detail=str(ex))
