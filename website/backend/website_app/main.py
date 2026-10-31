from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from website_app import auth
from website_app import consultations
from website_app.db import get_sessionmaker, DBNotEnabledError
from website_app.errors import AppException, exception_handler, success
from website_app.news.routes import router, public_api, public_pages
from website_app.integrations.routes import router as integrations_router

app = FastAPI(title='跃科官网独立服务', docs_url=None, redoc_url=None, openapi_url=None)
app.add_exception_handler(AppException, exception_handler)
app.include_router(auth.router, prefix='/api')
app.include_router(consultations.router, prefix='/api')
app.include_router(router, prefix='/api')
app.include_router(public_api, prefix='/api')
app.include_router(public_pages)
app.include_router(integrations_router, prefix='/api')

@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    # Never echo password or submitted article bodies in validation errors.
    return JSONResponse({'code': 422001, 'message': '提交内容格式不正确，请检查必填项和长度。', 'data': None}, status_code=422)

@app.exception_handler(SQLAlchemyError)
@app.exception_handler(DBNotEnabledError)
async def unavailable(request, exc):
    return JSONResponse({'code': 503001, 'message': '官网数据库暂不可用，请稍后重试。', 'data': None}, status_code=503)

@app.middleware('http')
async def headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.url.path.startswith(('/api/manage', '/api/auth')):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response

@app.get('/api/health')
def health():
    with get_sessionmaker()() as db:
        db.execute(text('SELECT 1'))
    return success({'service': 'website', 'database': 'available'})
