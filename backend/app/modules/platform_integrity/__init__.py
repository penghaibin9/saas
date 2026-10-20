"""PLAT-A frozen evidence and integrity federation primitives."""

from .contracts import FrozenPackageResult, PackageArtifactRef
from .frozen_package_service import build_frozen_package

__all__ = ["FrozenPackageResult", "PackageArtifactRef", "build_frozen_package"]
