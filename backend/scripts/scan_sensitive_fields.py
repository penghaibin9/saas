#!/usr/bin/env python3
"""只读扫描敏感字段：统计密文 / 疑似明文 / 解密失败。不自动修改生产数据。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args()

    from app.core.field_crypto import decrypt_field, looks_like_fernet
    from app.db.session import db_enabled, get_sessionmaker
    from sqlalchemy import select

    if not db_enabled():
        print(json.dumps({"ok": False, "error": "database_disabled"}, ensure_ascii=False))
        return 2

    from app.models import User
    db = get_sessionmaker()()
    report = {
        "table": "t_user.phone_encrypted",
        "scanned": 0,
        "ciphertext": 0,
        "likely_plaintext": 0,
        "decrypt_failed": 0,
        "empty": 0,
        "plaintextSamples": [],  # 仅 ID，不含明文
        "failedSamples": [],
        "remediation": "使用安全回填工具按 ID 列表加密；本脚本不改写数据",
    }
    try:
        rows = db.scalars(select(User).where(User.is_deleted.is_(False)).limit(args.limit)).all()
        for u in rows:
            report["scanned"] += 1
            raw = getattr(u, "phone_encrypted", None)
            if not raw:
                report["empty"] += 1
                continue
            text = str(raw)
            if looks_like_fernet(text):
                try:
                    decrypt_field(text, allow_legacy_plaintext=False)
                    report["ciphertext"] += 1
                except Exception:
                    report["decrypt_failed"] += 1
                    report["failedSamples"].append(u.id)
            else:
                # 疑似明文：全数字且长度像手机号
                if text.isdigit() and 11 <= len(text) <= 15:
                    report["likely_plaintext"] += 1
                    report["plaintextSamples"].append(u.id)
                elif looks_like_fernet(text):
                    report["decrypt_failed"] += 1
                    report["failedSamples"].append(u.id)
                else:
                    report["likely_plaintext"] += 1
                    report["plaintextSamples"].append(u.id)
    finally:
        db.close()

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
