"""Compatibility facade for canonical System Admin Data Exchange router.

Frozen pre-I1/I2 implementation lives in
``app.modules.system_admin.routers.data_exchange_bundle``. Runtime adapters make
GET pure read and move identity parsing to explicit worker commands.
"""
from app.modules.system_admin.routers import data_exchange_bundle as _bundle
from app.modules.system_admin.routers import data_exchange_router as _router
from app.modules.system_admin.routers.data_exchange_bundle import *  # noqa: F401,F403

router = _router.router
validate_identity_import = _router.validate_identity_import
import_job_detail = _router.import_job_detail
retry_import = _router.retry_import
process_identity_import = _router.process_identity_import


def __getattr__(name: str):
    if hasattr(_router, name):
        return getattr(_router, name)
    return getattr(_bundle, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_bundle)) | set(dir(_router)))
