"""PLAT-B compliance federation.

This package normalizes read-only assessments from domain authorities.  It must
never become a second rule engine or import domain writer helpers.
"""

from .providers import ComplianceFederation, default_federation
from .schemas import (
    ComplianceItem,
    ComplianceState,
    DomainComplianceAssessment,
    MaterialConstraint,
    MaterialConstraintState,
    PolicyRef,
    PolicyRefBindingMode,
    ProviderMode,
    SubjectRef,
)

__all__ = [
    "ComplianceFederation",
    "ComplianceItem",
    "ComplianceState",
    "DomainComplianceAssessment",
    "MaterialConstraint",
    "MaterialConstraintState",
    "PolicyRef",
    "PolicyRefBindingMode",
    "ProviderMode",
    "SubjectRef",
    "default_federation",
]
