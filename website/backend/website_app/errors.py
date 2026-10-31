from fastapi import Request
from fastapi.responses import JSONResponse

class AppException(Exception):
    def __init__(self, code, message, http_status=400):
        self.code, self.message, self.http_status = code, message, http_status

def success(data=None, message='操作成功'):
    return {'code': 0, 'data': data, 'message': message}

async def exception_handler(request: Request, exc: AppException):
    return JSONResponse({'code': exc.http_status * 1000 + 1, 'message': exc.message, 'data': None}, status_code=exc.http_status)
