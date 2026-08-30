"""PLAT-D private business-search and Todo-collaboration implementation.

The package is deliberately unregistered during C0-C4.  Shared API/router,
model registry, workbench and migration wiring belongs to the later serial
integration slot.
"""

from .navigation import NavigationTargetResolver
from .schemas import NavigationTarget, SearchContext, SearchHit

__all__ = ["NavigationTarget", "NavigationTargetResolver", "SearchContext", "SearchHit"]
