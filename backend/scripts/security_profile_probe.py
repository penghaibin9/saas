"""Security image probes. No application import, secret output or database writes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ("shared/contracts/module-manifest.json", "shared/contracts/permission-catalog.json")
WRITABLE = ("backend/uploads", "backend/exports", "backend/data")


def image_contract(root: Path = ROOT) -> None:
    if not hasattr(os, "geteuid") or os.geteuid() != 10001:
        raise RuntimeError("NONROOT_UID_REQUIRED")
    for relative in CONTRACTS:
        path = root / relative
        if path.is_symlink() or not json.loads(path.read_text(encoding="utf-8")):
            raise RuntimeError("RUNTIME_CONTRACT_MISSING")
    if os.access(root / "backend/app", os.W_OK) or os.access(root / "shared", os.W_OK):
        raise RuntimeError("APPLICATION_CODE_WRITABLE")


def filesystem(root: Path = ROOT) -> None:
    image_contract(root)
    for relative in WRITABLE:
        folder = root / relative
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError("WRITABLE_DIRECTORY_INVALID")
        # Only create/delete a uniquely named probe file, never modify business data.
        with tempfile.TemporaryFile(dir=folder) as stream:
            stream.write(b"probe")
            stream.flush()


def prepare_storage(root: Path = ROOT) -> None:
    """One-shot owner repair for EMPTY fresh volumes only; no recursive chown."""
    if os.geteuid() != 0:
        raise RuntimeError("STORAGE_PREPARATION_REQUIRES_OWNER")
    for relative in WRITABLE:
        folder = root / relative
        info = folder.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeError("STORAGE_DIRECTORY_INVALID")
        if (info.st_uid, info.st_gid) == (10001, 10001) and info.st_mode & 0o777 == 0o770:
            continue
        if next(folder.iterdir(), None) is not None:
            raise RuntimeError("NONEMPTY_VOLUME_REQUIRES_REVIEWED_MIGRATION")
        # With only CHOWN capability, chmod is legal while this process owns it.
        if info.st_uid != 0:
            raise RuntimeError("UNEXPECTED_EMPTY_VOLUME_OWNER")
        folder.chmod(0o770)
        os.chown(folder, 10001, 10001, follow_symlinks=False)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def ready() -> None:
    token = os.environ.get("INTERNAL_OPS_TOKEN", "")
    if not token:
        raise RuntimeError("OPS_TOKEN_REQUIRED")
    request = Request("http://127.0.0.1:8000/health/ready", headers={"X-Ops-Token": token})
    # Never send a local ops credential to an HTTP_PROXY from the environment.
    with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=5) as response:
        result = json.loads(response.read(65536))
        if response.status != 200 or result.get("status") != "READY":
            raise RuntimeError("APPLICATION_NOT_READY")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("image", "filesystem", "prepare-storage", "ready"))
    args = parser.parse_args(argv)
    try:
        {"image": image_contract, "filesystem": filesystem,
         "prepare-storage": prepare_storage, "ready": ready}[args.action]()
    except Exception as exc:
        print(json.dumps({"probePassed": False, "action": args.action, "errorType": type(exc).__name__}))
        return 1
    print(json.dumps({"probePassed": True, "action": args.action}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
