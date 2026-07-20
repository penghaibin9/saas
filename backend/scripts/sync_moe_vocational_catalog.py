"""同步教育部《职业教育专业目录（2021年）》官方 DOCX 附件。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx
from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import NationalMajorCatalog, NationalStandardSource  # noqa: E402

SOURCE_URL = "https://hudong.moe.gov.cn/srcsite/A07/moe_953/202103/W020210319595911145604.docx"
NOTICE_URL = "https://www.moe.gov.cn/srcsite/A07/moe_953/202103/t20210319_521135.html"
LEVEL_TABLES = {
    0: ("SECONDARY_VOCATIONAL", 358, "中等职业教育"),
    1: ("HIGHER_VOCATIONAL_SPECIALIST", 744, "高等职业教育专科"),
    2: ("VOCATIONAL_BACHELOR", 247, "高等职业教育本科"),
}
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _download() -> bytes:
    parsed = urlparse(SOURCE_URL)
    if parsed.scheme != "https" or parsed.netloc != "hudong.moe.gov.cn":
        raise RuntimeError("目录附件 URL 非教育部官方地址")
    response = httpx.get(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"},
                         timeout=90, follow_redirects=True)
    response.raise_for_status()
    if response.url.host not in {"hudong.moe.gov.cn", "www.moe.gov.cn"}:
        raise RuntimeError(f"目录附件重定向到非教育部域名：{response.url}")
    return response.content


def parse_catalog(data: bytes) -> list[dict]:
    if not data.startswith(b"PK"):
        raise RuntimeError("目录附件不是有效 DOCX 文件")
    with zipfile.ZipFile(BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    tables = root.findall(".//w:tbl", NS)
    if len(tables) < 3:
        raise RuntimeError("目录附件未找到三个办学层次表格")
    result = []
    for table_index, (level, expected, level_name) in LEVEL_TABLES.items():
        category_code = category_name = class_code = class_name = ""
        for row in tables[table_index].findall("./w:tr", NS):
            cells = []
            for cell in row.findall("./w:tc", NS):
                text = "".join(node.text or "" for node in cell.findall(".//w:t", NS))
                cells.append(re.sub(r"\s+", "", text))
            if not cells:
                continue
            unique = {value for value in cells if value}
            if len(unique) == 1:
                value = next(iter(unique))
                category = re.match(r"^(\d{2})(.+大类)$", value)
                major_class = re.match(r"^(\d{4})(.+类)$", value)
                if category:
                    category_code, category_name = category.groups()
                elif major_class:
                    class_code, class_name = major_class.groups()
                continue
            if len(cells) < 3 or not re.match(r"^\d+$", cells[0]):
                continue
            code_match = re.match(r"^(\d{6,8}[A-Z]?)$", cells[1])
            if not code_match or not category_code or not class_code:
                continue
            result.append({"educationLevel": level, "educationLevelName": level_name,
                           "categoryCode": category_code, "categoryName": category_name,
                           "majorClassCode": class_code, "majorClassName": class_name,
                           "majorCode": code_match.group(1), "majorName": cells[2]})
        actual = sum(item["educationLevel"] == level for item in result)
        if actual != expected:
            raise RuntimeError(f"目录数量门禁失败：{level} 应为 {expected}，实际 {actual}")
    return result


def apply_catalog(rows: list[dict], source_sha256: str) -> dict:
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(NationalStandardSource).where(
            NationalStandardSource.source_key == "MOE_VOCATIONAL_CATALOG",
            NationalStandardSource.version_label == "2021",
            NationalStandardSource.is_deleted.is_(False))).first()
        if not source:
            source = NationalStandardSource(source_key="MOE_VOCATIONAL_CATALOG",
                source_type="PROFESSIONAL_CATALOG", title="职业教育专业目录（2021年）",
                publisher="中华人民共和国教育部", version_label="2021", source_url=NOTICE_URL,
                published_date=date(2021, 3, 12), is_official=True,
                copyright_policy="OFFICIAL_METADATA", retrieval_status="RUNNING",
                item_count=len(rows), metadata_json={})
            db.add(source); db.flush()
        source.item_count = len(rows); source.manifest_sha256 = source_sha256
        source.retrieval_status = "RUNNING"
        for item in rows:
            major = db.scalars(select(NationalMajorCatalog).where(
                NationalMajorCatalog.catalog_version == "2021",
                NationalMajorCatalog.education_level == item["educationLevel"],
                NationalMajorCatalog.major_code == item["majorCode"],
                NationalMajorCatalog.is_deleted.is_(False))).first()
            values = {"source_id": source.id, "education_level": item["educationLevel"],
                      "category_code": item["categoryCode"], "category_name": item["categoryName"],
                      "major_class_code": item["majorClassCode"],
                      "major_class_name": item["majorClassName"], "major_name": item["majorName"],
                      "directory_status": "ACTIVE", "effective_date": date(2021, 3, 12)}
            if not major:
                major = NationalMajorCatalog(catalog_version="2021", major_code=item["majorCode"],
                    metadata_json={"officialCatalog": True, "standardCovered": False}, **values)
                db.add(major)
            else:
                for key, value in values.items():
                    setattr(major, key, value)
                metadata = dict(major.metadata_json or {})
                metadata["officialCatalog"] = True
                major.metadata_json = metadata; major.version += 1
        db.flush()
        stored = db.scalar(select(func.count(NationalMajorCatalog.id)).where(
            NationalMajorCatalog.catalog_version == "2021",
            NationalMajorCatalog.is_deleted.is_(False))) or 0
        source.retrieval_status = "COMPLETE" if stored == len(rows) else "PARTIAL"
        source.metadata_json = {"expected": 1349, "stored": stored,
                                "levels": {level: sum(x["educationLevel"] == level for x in rows)
                                           for level, _expected, _name in LEVEL_TABLES.values()}}
        db.commit()
        return {"catalogRows": len(rows), "stored": stored,
                "retrievalStatus": source.retrieval_status, "sourceSha256": source_sha256}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--input", type=Path, help="使用已下载的教育部 DOCX 附件")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes() if args.input else _download()
    rows = parse_catalog(data)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {level: sum(x["educationLevel"] == level for x in rows)
              for level, _expected, _name in LEVEL_TABLES.values()}
    sha = hashlib.sha256(data).hexdigest()
    print(json.dumps({"catalogRows": len(rows), "levels": counts, "sourceSha256": sha},
                     ensure_ascii=False), flush=True)
    if args.apply:
        print(json.dumps(apply_catalog(rows, sha), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
