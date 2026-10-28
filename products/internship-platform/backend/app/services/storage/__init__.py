from __future__ import annotations
import shutil
from pathlib import Path
from app.config import settings

class LocalStorageBackend:
    def __init__(self):
        self.root=Path(settings.FILE_STORAGE_DIR).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.staging=self.root/"_staging"
        self.staging.mkdir(parents=True,exist_ok=True)
    def _safe(self,key):
        rel=Path(str(key or "").replace("\\","/"))
        if rel.is_absolute() or ".." in rel.parts: raise ValueError("invalid storage key")
        path=(self.root/rel).resolve()
        if self.root not in path.parents and path!=self.root: raise ValueError("invalid storage key")
        return path
    def staging_path(self,key):
        name=Path(str(key)).name
        return self.staging/name
    def persist(self,key,source):
        target=self._safe(key);target.parent.mkdir(parents=True,exist_ok=True)
        source=Path(source)
        if source.resolve()!=target.resolve(): shutil.move(str(source),str(target))
        return target
    def fetch_local(self,key):
        path=self._safe(key)
        return path if path.exists() else None

_backend=None
def get_backend():
    global _backend
    if _backend is None:_backend=LocalStorageBackend()
    return _backend
