"""PLAT-C document intelligence and lifecycle projection private package.

This package is deliberately not registered in shared routers or model registries yet.
PLAT-C's migration/registration slot may only run after the A+B integration head is
available; private services and characterization tests can be developed independently.
"""

from app.modules.platform.document_lifecycle.exact_file_version_read_port import (
    ExactFileVersionReadPort,
    ExactSourceVersion,
    IExactFileVersionReadPort,
)

__all__ = (
    "ExactFileVersionReadPort",
    "ExactSourceVersion",
    "IExactFileVersionReadPort",
)
