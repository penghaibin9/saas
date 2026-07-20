"""同步教育部 2025 年 758 项职业教育专业教学标准。

默认只枚举并校验官方清单；--apply 才下载 PDF、提取正文和 11 个章节并幂等入库。
来源域名与目录固定，拒绝调用方传入任意 URL，避免把采集器变成 SSRF/通用下载器。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import (NationalMajorCatalog, NationalStandardDocument,  # noqa: E402
                        NationalStandardSection, NationalStandardSource)

BASE_URL = "https://www.moe.gov.cn/s78/A07/zcs_ztzl/2017_zt06/17zt06_bznr/bznr_zyjyzyjxbz/"
LEVELS = {
    "SECONDARY_VOCATIONAL": ("zyjyzyjxbz_zz/", 223, "中等职业教育"),
    # 教育部发布口径为 471；当前公开目录可核验 PDF 为 465，另 6 项未公开列出。
    "HIGHER_VOCATIONAL_SPECIALIST": ("gdzyjy_zk/", 465, "高等职业教育专科"),
    "VOCATIONAL_BACHELOR": ("gdzyjy_bk/", 64, "高等职业教育本科"),
}
OFFICIAL_PUBLISHED_COUNTS = {
    "SECONDARY_VOCATIONAL": 223,
    "HIGHER_VOCATIONAL_SPECIALIST": 471,
    "VOCATIONAL_BACHELOR": 64,
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
           "Referer": BASE_URL, "Accept-Language": "zh-CN,zh;q=0.9"}
MAX_PDF_BYTES = 20 * 1024 * 1024
PAGE_CACHE_DIR = BACKEND_ROOT.parent / ".cache" / "moe-professional-standards"
PAGE_CACHE_TTL_SECONDS = 6 * 60 * 60
SECTION_TITLES = {
    1: "概述", 2: "专业名称（专业代码）", 3: "入学基本要求", 4: "基本修业年限",
    5: "职业面向", 6: "培养目标", 7: "培养规格", 8: "课程设置及学时安排",
    9: "师资队伍", 10: "教学条件", 11: "质量保障和毕业要求",
}
SECTION_TOKENS = {1: "概述", 2: "专业名称", 3: "入学基本要求", 4: "基本修业年限",
                  5: "职业面向", 6: "培养目标", 7: "培养规格", 8: "课程设置",
                  9: "师资队伍", 10: "教学条件", 11: "质量保障"}
FULLWIDTH_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９", "0123456789")


def _official(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == "www.moe.gov.cn" and url.startswith(BASE_URL)


def _links(page_url: str, content: str) -> list[tuple[str, str]]:
    rows = []
    for href, raw in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', content, re.I | re.S):
        url = urljoin(page_url, html.unescape(href))
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(raw))).strip()
        if _official(url):
            rows.append((url, text))
    return rows


def _get_response(client: httpx.Client, url: str, timeout_label: str = "页面") -> httpx.Response:
    if not _official(url):
        raise RuntimeError(f"拒绝非教育部标准目录 URL：{url}")
    last_error = None
    for attempt in range(4):
        try:
            response = client.get(url)
            final = response.url
            if final.host != "www.moe.gov.cn":
                raise RuntimeError(f"{timeout_label}重定向到非教育部域名：{final}")
            if final.scheme != "https":
                secure_url = str(final.copy_with(scheme="https"))
                response = client.get(secure_url)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"{timeout_label}连续重试失败：{url}；{last_error}")


def _get_text(client: httpx.Client, url: str) -> str:
    response = _get_response(client, url)
    return response.content.decode("utf-8", "replace")


def _fetch_text(url: str) -> str:
    PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = PAGE_CACHE_DIR / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < PAGE_CACHE_TTL_SECONDS:
        return cache_file.read_text(encoding="utf-8")
    with httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True) as client:
        content = _get_text(client, url)
    cache_file.write_text(content, encoding="utf-8")
    return content


def crawl_manifest() -> list[dict]:
    manifest: dict[tuple[str, str], dict] = {}
    with httpx.Client(headers=HEADERS, timeout=40, follow_redirects=True) as client:
        for level, (relative, _expected, level_name) in LEVELS.items():
            level_url = urljoin(BASE_URL, relative)
            level_links = _links(level_url, _get_text(client, level_url))
            category_pages = [(url, text.replace(">>", "").strip()) for url, text in level_links
                              if url.endswith("/") and url != level_url and "大类" in text]
            class_pages: dict[str, tuple[str, str]] = {}
            # 教育部层级首页已经按“专业大类 -> 专业类”顺序列出了全部专业类。
            # 直接按该顺序归属大类，避免部分大类子页的栏目分页漏掉专业类。
            current_category = ""
            for url, raw_text in level_links:
                text = raw_text.replace(">>", "").replace("更多", "").strip()
                if url.endswith("/") and url != level_url and "大类" in text:
                    current_category = text
                    continue
                if current_category and url.endswith("/") and url != level_url and "类" in text:
                    class_pages[url] = (text, current_category)

            # 兼容教育部后续把专业类链接从层级首页折叠回大类子页的情况。
            if not class_pages:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    category_futures = {pool.submit(_fetch_text, url): (url, name)
                                        for url, name in category_pages}
                    for future in as_completed(category_futures):
                        category_url, category_name = category_futures[future]
                        for url, raw_text in _links(category_url, future.result()):
                            text = raw_text.replace(">>", "").replace("更多", "").strip()
                            if url.endswith("/") and url != category_url and "类" in text:
                                class_pages[url] = (text, category_name)
            with ThreadPoolExecutor(max_workers=6) as pool:
                class_futures = {pool.submit(_fetch_text, url): (url, names)
                                 for url, names in class_pages.items()}
                for future in as_completed(class_futures):
                    class_url, (class_name, category_name) = class_futures[future]
                    for pdf_url, label in _links(class_url, future.result()):
                        if not pdf_url.lower().endswith(".pdf"):
                            continue
                        # K 是教育部专业目录中的国家控制布点专业后缀，不得丢弃。
                        match = re.match(r"^(\d{6,8}[A-Z]?)\s+(.+?)(?:\s+(20\d{2}-\d{2}-\d{2}))?$", label)
                        if not match:
                            continue
                        major_code, major_name, published = match.groups()
                        published = published or "2025-02-11"
                        manifest[(level, major_code)] = {
                            "educationLevel": level, "educationLevelName": level_name,
                            "categoryCode": major_code[:2], "categoryName": category_name,
                            "majorClassCode": major_code[:4], "majorClassName": class_name,
                            "majorCode": major_code, "majorName": major_name,
                            "publishedDate": published, "sourceUrl": pdf_url,
                        }
            print(json.dumps({"progress": level, "categories": len(category_pages),
                              "classes": len(class_pages),
                              "documents": sum(x[0] == level for x in manifest)}, ensure_ascii=False), flush=True)
    rows = sorted(manifest.values(), key=lambda x: (x["educationLevel"], x["majorCode"]))
    counts = {level: sum(x["educationLevel"] == level for x in rows) for level in LEVELS}
    errors = {level: {"expected": expected, "actual": counts[level]}
              for level, (_url, expected, _name) in LEVELS.items() if counts[level] != expected}
    if errors:
        raise RuntimeError(f"教育部清单数量门禁失败，拒绝入库：{json.dumps(errors, ensure_ascii=False)}")
    return rows


def extract_sections(full_text: str) -> list[dict]:
    positions = []
    for number, token in SECTION_TOKENS.items():
        heading = r"(?:课程设置|课程及学时安排)" if number == 8 else re.escape(token)
        pattern = re.compile(rf"(?m)^\s*(?:\d+\s+)?{number}\s+{heading}[^\n]*$")
        match = pattern.search(full_text)
        if match:
            positions.append((number, match.start()))
    positions.sort(key=lambda item: item[1])
    sections = []
    for index, (number, start) in enumerate(positions):
        end = positions[index + 1][1] if index + 1 < len(positions) else len(full_text)
        content = full_text[start:end].strip()
        sections.append({"sectionCode": f"SECTION_{number:02d}", "sectionNo": number,
                         "sectionTitle": SECTION_TITLES[number], "content": content,
                         "contentSha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    return sections


def _download_extract(item: dict) -> dict:
    # PDF parsing is only needed after a verified download. Keep pypdf lazy so
    # catalog/search tests and metadata-only runs do not load its native image
    # stack during module collection.
    from pypdf import PdfReader

    with httpx.Client(headers=HEADERS, timeout=90, follow_redirects=True) as client:
        response = _get_response(client, item["sourceUrl"], "PDF")
        content = response.content
    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise RuntimeError("PDF 类型或大小不符合安全门禁")
    reader = PdfReader(BytesIO(content))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    text = re.sub(r"[ \t]+", " ", text).replace("\x00", "").translate(
        FULLWIDTH_DIGIT_TRANSLATION).strip()
    if len(text) < 500:
        raise RuntimeError("PDF 正文提取字符过少")
    sections = extract_sections(text)
    if len(sections) != len(SECTION_TITLES):
        raise RuntimeError(f"只识别到 {len(sections)} 个标准章节，要求完整识别 11 章")
    return {**item, "sourceSha256": hashlib.sha256(content).hexdigest(),
            "sourceFileName": Path(urlparse(item["sourceUrl"]).path).name,
            "pageCount": len(reader.pages), "fullText": text, "charCount": len(text),
            "sections": sections, "textStatus": "EXTRACTED", "extractionError": ""}


def _manifest_hash(manifest: list[dict]) -> str:
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, list):
        raise RuntimeError("清单必须是 JSON 数组")
    required = {"educationLevel", "educationLevelName", "categoryCode", "categoryName",
                "majorClassCode", "majorClassName", "majorCode", "majorName",
                "publishedDate", "sourceUrl"}
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(manifest):
        if not isinstance(item, dict) or not required.issubset(item):
            raise RuntimeError(f"清单第 {index + 1} 项字段不完整")
        if item["educationLevel"] not in LEVELS or not _official(item["sourceUrl"]):
            raise RuntimeError(f"清单第 {index + 1} 项层级或来源 URL 非法")
        key = (item["educationLevel"], item["majorCode"])
        if key in seen:
            raise RuntimeError(f"清单存在重复专业：{key}")
        seen.add(key)
    counts = {level: sum(x["educationLevel"] == level for x in manifest) for level in LEVELS}
    errors = {level: {"expected": expected, "actual": counts[level]}
              for level, (_url, expected, _name) in LEVELS.items() if counts[level] != expected}
    if errors:
        raise RuntimeError(f"清单数量门禁失败，拒绝入库：{json.dumps(errors, ensure_ascii=False)}")
    return manifest


def apply_manifest(manifest: list[dict], workers: int = 4, limit: int = 0,
                   offset: int = 0) -> dict:
    if offset < 0 or offset >= len(manifest):
        raise RuntimeError(f"offset 必须在 0 到 {len(manifest) - 1} 之间")
    selected = manifest[offset:offset + limit] if limit else manifest[offset:]
    extracted, failed = [], []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = {pool.submit(_download_extract, item): item for item in selected}
        for completed, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            try:
                extracted.append(future.result())
            except Exception as exc:  # noqa: BLE001
                failed.append({**item, "textStatus": "EXTRACTION_FAILED",
                               "extractionError": str(exc)[:1000], "sections": []})
            if completed % 25 == 0 or completed == len(selected):
                print(json.dumps({"downloadProgress": completed, "total": len(selected),
                                  "extracted": len(extracted), "failed": len(failed)},
                                 ensure_ascii=False), flush=True)

    db = get_sessionmaker()()
    try:
        source = db.scalars(select(NationalStandardSource).where(
            NationalStandardSource.source_key == "MOE_PROFESSIONAL_TEACHING_STANDARD",
            NationalStandardSource.version_label == "2025",
            NationalStandardSource.is_deleted.is_(False))).first()
        if not source:
            source = NationalStandardSource(source_key="MOE_PROFESSIONAL_TEACHING_STANDARD",
                source_type="PROFESSIONAL_TEACHING_STANDARD",
                title="758项新版职业教育专业教学标准", version_label="2025",
                source_url=BASE_URL, published_date=date(2025, 2, 11), is_official=True,
                copyright_policy="INTERNAL_SEARCH_LINK_SOURCE", retrieval_status="RUNNING",
                item_count=len(manifest), metadata_json={"expected": 758, "sectionCount": 11})
            db.add(source); db.flush()
        source.item_count = len(manifest); source.manifest_sha256 = _manifest_hash(manifest)
        source.last_crawled_at = datetime.now(UTC).replace(tzinfo=None); source.retrieval_status = "RUNNING"
        for item in [*extracted, *failed]:
            major = db.scalars(select(NationalMajorCatalog).where(
                NationalMajorCatalog.catalog_version == "2021",
                NationalMajorCatalog.education_level == item["educationLevel"],
                NationalMajorCatalog.major_code == item["majorCode"],
                NationalMajorCatalog.is_deleted.is_(False))).first()
            if not major:
                major = NationalMajorCatalog(source_id=source.id, catalog_version="2021",
                    education_level=item["educationLevel"], category_code=item["categoryCode"],
                    category_name=item["categoryName"], major_class_code=item["majorClassCode"],
                    major_class_name=item["majorClassName"], major_code=item["majorCode"],
                    major_name=item["majorName"], directory_status="ACTIVE",
                    effective_date=date(2021, 3, 12), metadata_json={"standardCovered": True})
                db.add(major); db.flush()
            standard_code = f"MOE-2025-{item['educationLevel']}-{item['majorCode']}"
            document = db.scalars(select(NationalStandardDocument).where(
                NationalStandardDocument.standard_code == standard_code,
                NationalStandardDocument.version_label == "2025",
                NationalStandardDocument.is_deleted.is_(False))).first()
            values = {"source_id": source.id, "major_catalog_id": major.id,
                      "title": f"{item['majorName']}专业教学标准（{item['educationLevelName']}）",
                      "education_level": item["educationLevel"], "major_code": item["majorCode"],
                      "major_name": item["majorName"], "published_date": date.fromisoformat(item["publishedDate"]),
                      "source_url": item["sourceUrl"], "source_file_name": item.get("sourceFileName"),
                      "source_sha256": item.get("sourceSha256"), "page_count": item.get("pageCount"),
                      "text_status": item["textStatus"], "full_text": item.get("fullText"),
                      "structured_json": {"sectionCodes": [x["sectionCode"] for x in item["sections"]]},
                      "char_count": item.get("charCount", 0), "status": "PUBLISHED",
                      "extraction_error": item.get("extractionError") or None}
            if not document:
                document = NationalStandardDocument(standard_code=standard_code, version_label="2025", **values)
                db.add(document); db.flush()
            else:
                for key, value in values.items(): setattr(document, key, value)
                document.version += 1; db.flush()
            active_codes = set()
            for section_data in item["sections"]:
                active_codes.add(section_data["sectionCode"])
                section = db.scalars(select(NationalStandardSection).where(
                    NationalStandardSection.document_id == document.id,
                    NationalStandardSection.section_code == section_data["sectionCode"])).first()
                if not section:
                    section = NationalStandardSection(document_id=document.id,
                        section_code=section_data["sectionCode"], section_no=section_data["sectionNo"],
                        section_title=section_data["sectionTitle"], content_text=section_data["content"],
                        content_sha256=section_data["contentSha256"])
                    db.add(section)
                else:
                    section.section_no = section_data["sectionNo"]; section.section_title = section_data["sectionTitle"]
                    section.content_text = section_data["content"]; section.content_sha256 = section_data["contentSha256"]
                    section.is_deleted = False; section.version += 1
            for old in db.scalars(select(NationalStandardSection).where(
                    NationalStandardSection.document_id == document.id,
                    NationalStandardSection.is_deleted.is_(False))).all():
                if old.section_code not in active_codes:
                    old.is_deleted = True; old.version += 1
        db.flush()
        total_extracted = db.scalar(select(func.count()).select_from(NationalStandardDocument).where(
            NationalStandardDocument.source_id == source.id,
            NationalStandardDocument.text_status == "EXTRACTED",
            NationalStandardDocument.is_deleted.is_(False))) or 0
        total_failed = db.scalar(select(func.count()).select_from(NationalStandardDocument).where(
            NationalStandardDocument.source_id == source.id,
            NationalStandardDocument.text_status == "EXTRACTION_FAILED",
            NationalStandardDocument.is_deleted.is_(False))) or 0
        source.retrieval_status = (
            "COMPLETE" if total_extracted == len(manifest) and total_failed == 0 else "PARTIAL"
        )
        source.metadata_json = {
            "officialPublishedCount": sum(OFFICIAL_PUBLISHED_COUNTS.values()),
            "publiclyAccessibleCount": len(manifest),
            "officialPublicGap": sum(OFFICIAL_PUBLISHED_COUNTS.values()) - len(manifest),
            "publicCountsByLevel": {
                level: sum(item["educationLevel"] == level for item in manifest)
                for level in LEVELS
            },
            "lastBatchOffset": offset, "lastBatchSelected": len(selected),
            "lastBatchExtracted": len(extracted), "lastBatchFailed": len(failed),
            "totalExtracted": total_extracted, "totalFailed": total_failed,
            "sectionCount": 11,
        }
        db.commit()
        return {"manifest": len(manifest), "offset": offset, "selected": len(selected),
                "extracted": len(extracted),
                "failed": len(failed), "manifestSha256": source.manifest_sha256,
                "totalExtracted": total_extracted, "totalFailed": total_failed,
                "retrievalStatus": source.retrieval_status,
                "failedItems": [{"majorCode": x["majorCode"], "error": x["extractionError"]} for x in failed]}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="下载全文并写入配置的数据库")
    parser.add_argument("--limit", type=int, default=0, help="仅用于开发验证；全量时必须为0")
    parser.add_argument("--offset", type=int, default=0, help="断点批次在清单中的起始偏移")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--manifest", type=Path, help="可选：写出官方清单 JSON")
    parser.add_argument("--manifest-input", type=Path,
                        help="读取先前已验证的官方清单，避开教育部栏目页临时不可用")
    args = parser.parse_args()
    if args.manifest_input:
        manifest = validate_manifest(json.loads(args.manifest_input.read_text(encoding="utf-8")))
    else:
        manifest = crawl_manifest()
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {level: sum(x["educationLevel"] == level for x in manifest) for level in LEVELS}
    print(json.dumps({"manifest": len(manifest), "levels": counts,
                      "manifestSha256": _manifest_hash(manifest)}, ensure_ascii=False))
    if args.apply:
        print(json.dumps(apply_manifest(manifest, args.workers, args.limit, args.offset), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
