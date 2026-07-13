"""把本地已存文件迁移到腾讯云 COS（一次性搬家工具）。

背景：历史文件字节都在服务器本地 UPLOAD_DIR。切到 COS 后端后，新文件自动上 COS，
但历史文件还在本地——本脚本按 t_file_object 台账把它们逐个上传到 COS，key 不变。
迁移只搬字节，t_file_object 表零改动（file_key 语义两后端相同）。

安全：
- 默认 dry-run，只清点不上传；确认无误再加 --commit 真正上传。
- 幂等：COS 已存在同 key 的对象默认跳过（--overwrite 可强制覆盖）。
- 只上传，不删本地原文件（搬完人工核对无误后，再决定是否清理本地盘）。

用法（在 backend/ 下，先在 .env 配好 COS_* 与 FILE_STORAGE_BACKEND=cos）：
    python scripts/migrate_files_to_cos.py            # dry-run 清点
    python scripts/migrate_files_to_cos.py --commit   # 真正上传
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local files to Tencent COS")
    parser.add_argument("--commit", action="store_true", help="真正上传（缺省仅 dry-run 清点）")
    parser.add_argument("--overwrite", action="store_true", help="COS 已存在同 key 也覆盖上传")
    args = parser.parse_args()

    if (settings.FILE_STORAGE_BACKEND or "").strip().lower() != "cos":
        print("FILE_STORAGE_BACKEND 不是 cos；请先在 .env 设 FILE_STORAGE_BACKEND=cos 并配好 COS_*。")
        return 2

    if not settings.DB_ENABLED:
        print("DB_ENABLED=false：迁移需读取 t_file_object 台账，请在真库模式下运行。")
        return 2

    from sqlalchemy import select
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    from app.services.storage.cos import CosStorageBackend
    from app.services.storage.local import LocalStorageBackend

    local = LocalStorageBackend()
    cos = CosStorageBackend()  # 配置缺失会在此抛 FILE_STORAGE_MISCONFIGURED

    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(FileObject).where(FileObject.status == "STORED")).all()
    finally:
        db.close()

    total = len(rows)
    uploaded = skipped_exists = missing_local = 0
    print(f"台账中 STORED 文件 {total} 个。模式：{'COMMIT 真上传' if args.commit else 'DRY-RUN 仅清点'}")
    for r in rows:
        key = r.file_key
        src = local.fetch_local(key)
        if not src:
            missing_local += 1
            print(f"  [缺本地] fileId={r.id} key={key}（本地盘找不到字节，跳过）")
            continue
        if not args.overwrite and cos.exists(key):
            skipped_exists += 1
            continue
        if args.commit:
            cos._client.put_object(Bucket=cos._bucket, Body=src.open("rb"), Key=key)
        uploaded += 1

    print("─" * 40)
    print(f"待上传/已上传：{uploaded}")
    print(f"COS 已存在跳过：{skipped_exists}")
    print(f"本地缺字节跳过：{missing_local}")
    if not args.commit:
        print("（dry-run，未真正上传。确认无误后加 --commit 执行。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
