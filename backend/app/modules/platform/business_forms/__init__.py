"""Schema-assisted forms owned by PLAT-B.

Definitions and immutable versions are platform-owned.  Submitted business
records and workflow state always remain in the source domain.
"""

from .domain_adapters import (
    BusinessFormCommandAdapterRegistry,
    BusinessFormDataAdapterRegistry,
    BusinessFormSubmissionService,
    DomainCommandResult,
    InternshipSpecialFilingCommandAdapter,
    InternshipSpecialFilingDataAdapter,
)
from .application_service import BusinessFormApplicationService
from .definition_service import BusinessFormDefinitionService
from .runtime import BusinessFormRuntimeValidator
from .schema_validator import BusinessFormSchemaValidator, compute_schema_hash
from .schemas import BusinessFormVersionDTO

__all__ = [
    "BusinessFormCommandAdapterRegistry",
    "BusinessFormDataAdapterRegistry",
    "BusinessFormApplicationService",
    "BusinessFormDefinitionService",
    "BusinessFormRuntimeValidator",
    "BusinessFormSchemaValidator",
    "BusinessFormSubmissionService",
    "BusinessFormVersionDTO",
    "DomainCommandResult",
    "InternshipSpecialFilingCommandAdapter",
    "InternshipSpecialFilingDataAdapter",
    "compute_schema_hash",
]
