"""同步教育部 2022 年 1349 个职业教育专业简介。

专业简介按“专业类 PDF”发布，本脚本把每份 PDF 拆成逐专业全文和结构化章节，
同时补齐 2021 专业目录。默认只发现并校验清单，--apply 才写数据库。
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
from pypdf import PdfReader
from sqlalchemy import func, select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import get_sessionmaker  # noqa: E402
from app.models import (NationalMajorCatalog, NationalStandardDocument,  # noqa: E402
                        NationalStandardSection, NationalStandardSource)

BASE_URL = "https://www.moe.gov.cn/s78/A07/zcs_ztzl/2017_zt06/17zt06_bznr/bznr_zdzyxxzyml/"
LEVELS = {
    "SECONDARY_VOCATIONAL": ("zhongzhi/", 358, "中等职业教育"),
    "HIGHER_VOCATIONAL_SPECIALIST": ("gaozhizhuan/", 744, "高等职业教育专科"),
    "VOCATIONAL_BACHELOR": ("gaozhiben/", 247, "高等职业教育本科"),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
           "Referer": BASE_URL, "Accept-Language": "zh-CN,zh;q=0.9"}
FULLWIDTH_DIGIT_TRANSLATION = str.maketrans("０１２３４５６７８９", "0123456789")
MAX_PDF_BYTES = 30 * 1024 * 1024
PAGE_CACHE_DIR = BACKEND_ROOT.parent / ".cache" / "moe-professional-profiles"
PDF_CACHE_DIR = BACKEND_ROOT.parent / ".cache" / "moe-professional-profile-pdfs"
PAGE_CACHE_TTL_SECONDS = 6 * 60 * 60
SECTION_HEADINGS = (
    "专业代码", "专业名称", "基本修业年限", "职业面向", "培养目标定位",
    "主要专业能力要求", "主要专业课程与实习实训", "职业类证书举例", "接续专业举例",
)
OCR_PAGE_OVERRIDES = {
    # 电子与信息大类职业本科专业简介 PDF 第 5 页只有扫描图，无文本层。
    # 本段经页面图像复核；仅在官方文件 SHA-256 不变时插入 310204 正文。
    "87d019b296fdddd0a9396ca72ba3f32f6ec917aeb991da31f3f108d235903f05": """
培养目标定位
本专业培养德智体美劳全面发展，掌握扎实的科学文化基础和信息传播理论、数字媒体技术、人机交互技术及相关法律法规等知识，具备对用户的研究分析能力，数字媒体内容设计和制作、数字媒体系统开发、系统集成、新媒体策划、全媒体运营与管理等能力，具有工匠精神和信息素养，能够从事数字媒体产品策划与设计、人机交互技术开发、新媒体后期制作、全媒体运营与管理等工作的高层次技术技能人才。
主要专业能力要求
1. 具备较强的数字媒体、艺术设计、媒体传播等知识整合与技术应用能力；
2. 具备制定数字媒体技术规程与方案、创新性解决技术难题的能力；
3. 具备数字图像处理技术，具备影像采集、整合、输出的能力；
4. 具备人机交互设计与制作技术，具备视觉设计能力；
5. 具备完成互联网广告、新媒体视频等数字作品的能力；
6. 具备三维虚拟仿真产品的设计、制作、开发和集成能力；
7. 具备全媒体融合统筹规划、执行管理与推进、内容规划评估与优化的能力；
8. 具备从事数字媒体技术研发、科技成果转化的能力；
9. 具有探究学习、终身学习和可持续发展的能力。
主要专业课程与实习实训
专业基础课程：数字媒体技术概论、艺术设计与美学、摄影摄像、计算机平面设计、数字音视频技术、人机交互技术、用户心理与行为分析、项目策划与文案写作。
专业核心课程：三维动画制作技术、计算机视觉技术应用、信息可视化技术、非线性编辑技术、虚拟现实应用开发、交互产品开发、媒体栏目包装、融合媒体策划与营销。
实习实训：对接真实职业场景或工作情境，在校内外进行视觉设计、交互设计、短视频合成与特效、媒体栏目包装等实训。在数字内容服务、影视节目制作等行业的数字媒体技术设计与应用企业、媒体内容策划制作企业、虚拟现实应用开发企业等单位进行岗位实习。
职业类证书举例
职业技能等级证书：数字媒体交互设计、数字创意建模、界面设计、虚拟现实应用开发、数字影像处理、新媒体运营
接续专业举例
接续专业硕士学位授予领域举例：计算机科学与技术、新闻与传播
""".strip(),
}


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


def _get(client: httpx.Client, url: str, label: str = "页面") -> httpx.Response:
    if not _official(url):
        raise RuntimeError(f"拒绝非教育部专业简介 URL：{url}")
    last_error = None
    for attempt in range(4):
        try:
            response = client.get(url)
            if response.url.host != "www.moe.gov.cn":
                raise RuntimeError(f"{label}重定向到非教育部域名：{response.url}")
            if response.url.scheme != "https":
                response = client.get(str(response.url.copy_with(scheme="https")))
            response.raise_for_status()
            return response
        except (httpx.HTTPError, RuntimeError) as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(1 + attempt)
    raise RuntimeError(f"{label}连续重试失败：{url}；{last_error}")


def _fetch_text(url: str) -> str:
    PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = PAGE_CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()}.html"
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < PAGE_CACHE_TTL_SECONDS:
        return cache_file.read_text(encoding="utf-8")
    with httpx.Client(headers=HEADERS, timeout=40, follow_redirects=True) as client:
        content = _get(client, url).content.decode("utf-8", "replace")
    cache_file.write_text(content, encoding="utf-8")
    return content


def crawl_class_manifest() -> list[dict]:
    manifest: dict[tuple[str, str], dict] = {}
    for level, (relative, _expected, level_name) in LEVELS.items():
        level_url = urljoin(BASE_URL, relative)
        level_links = _links(level_url, _fetch_text(level_url))
        categories = [(url, text.replace(">>", "").strip()) for url, text in level_links
                      if url.endswith("/") and url != level_url and "大类" in text]
        page_links = [(level_url, "")]
        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = {pool.submit(_fetch_text, url): (url, name) for url, name in categories}
            for future in as_completed(futures):
                category_url, category_name = futures[future]
                page_links.extend((url, f"{category_name}\t{text}")
                                  for url, text in _links(category_url, future.result()))
        # 层级首页会直接列出部分专业类；分类页列出该大类全部专业类。
        page_links.extend((url, text) for url, text in level_links)
        current_category = ""
        for url, raw_text in page_links:
            if "\t" in raw_text:
                category_name, raw_text = raw_text.split("\t", 1)
            else:
                category_name = current_category
            clean = raw_text.replace(">>", "").strip()
            if "大类" in clean and not url.lower().endswith(".pdf"):
                current_category = clean
                continue
            if not url.lower().endswith(".pdf"):
                continue
            match = re.match(r"^(\d{4})\s+(.+?)(?:\s*20\d{2}-\d{2}-\d{2})?$", clean)
            if not match:
                continue
            class_code, class_name = match.groups()
            manifest[(level, class_code)] = {
                "educationLevel": level, "educationLevelName": level_name,
                "categoryCode": class_code[:2], "categoryName": category_name or "",
                "majorClassCode": class_code, "majorClassName": class_name.strip(),
                "sourceUrl": url,
            }
        print(json.dumps({"progress": level, "categories": len(categories),
                          "classDocuments": sum(key[0] == level for key in manifest)},
                         ensure_ascii=False), flush=True)
    return sorted(manifest.values(), key=lambda x: (x["educationLevel"], x["majorClassCode"]))


def _normalize(text: str) -> str:
    # 部分教育部 PDF 文本层会在专业代码前后插入 U+1E24 字形占位符。
    return re.sub(r"[ \t]+", " ", text).replace("\x00", "").replace("Ḥ", "").translate(
        FULLWIDTH_DIGIT_TRANSLATION).strip()


def _split_profiles(full_text: str) -> list[dict]:
    matches = list(re.finditer(r"(?m)^\s*专业代码\s+(\d{6,8}[A-Z]?)\s*$", full_text))
    profiles = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(full_text)
        content = full_text[match.start():end].strip()
        name_match = re.search(r"(?m)^\s*专业名称\s+([^\n]+?)\s*$", content)
        if not name_match:
            continue
        headings = []
        for order, heading in enumerate(SECTION_HEADINGS, start=1):
            found = re.search(rf"(?m)^\s*{re.escape(heading)}(?:\s+[^\n]+)?\s*$", content)
            if found:
                headings.append((order, heading, found.start()))
        headings.sort(key=lambda item: item[2])
        sections = []
        for position, (order, heading, start) in enumerate(headings):
            section_end = headings[position + 1][2] if position + 1 < len(headings) else len(content)
            section_text = content[start:section_end].strip()
            sections.append({"sectionCode": f"PROFILE_{order:02d}", "sectionNo": order,
                             "sectionTitle": heading, "content": section_text,
                             "contentSha256": hashlib.sha256(section_text.encode()).hexdigest()})
        limited = "（略）" in content and len(content) < 200
        profiles.append({"majorCode": match.group(1), "majorName": name_match.group(1).strip(),
                         "fullText": content, "charCount": len(content), "sections": sections,
                         "textStatus": "METADATA_ONLY" if limited else "EXTRACTED"})
    return profiles


def _download_class(item: dict) -> dict:
    PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = PDF_CACHE_DIR / f"{hashlib.sha256(item['sourceUrl'].encode()).hexdigest()}.pdf"
    if cache_file.exists():
        data = cache_file.read_bytes()
    else:
        with httpx.Client(headers=HEADERS, timeout=90, follow_redirects=True) as client:
            data = _get(client, item["sourceUrl"], "PDF").content
        cache_file.write_bytes(data)
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise RuntimeError("专业简介 PDF 类型或大小不符合安全门禁")
    reader = PdfReader(BytesIO(data))
    text = _normalize("\n".join((page.extract_text() or "") for page in reader.pages))
    source_sha256 = hashlib.sha256(data).hexdigest()
    override = OCR_PAGE_OVERRIDES.get(source_sha256)
    if override:
        profile_start = text.find("专业代码 310204")
        next_profile = text.find("专业代码 310205", profile_start)
        if profile_start >= 0 and next_profile > profile_start:
            segment = text[profile_start:next_profile]
            if "培养目标定位" not in segment:
                insert_at = text.find("\n224 \n", profile_start, next_profile)
                insert_at = insert_at if insert_at >= 0 else next_profile
                text = f"{text[:insert_at]}\n{override}\n{text[insert_at:]}"
    profiles = _split_profiles(text)
    if not profiles:
        raise RuntimeError("专业类 PDF 未识别到任何专业简介")
    return {**item, "sourceSha256": source_sha256,
            "sourceFileName": Path(urlparse(item["sourceUrl"]).path).name,
            "pageCount": len(reader.pages), "profiles": profiles}


def build_profile_manifest(class_manifest: list[dict], workers: int = 1) -> tuple[list[dict], list[dict]]:
    profiles, failed = [], []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 3))) as pool:
        futures = {pool.submit(_download_class, item): item for item in class_manifest}
        for completed, future in enumerate(as_completed(futures), start=1):
            item = futures[future]
            try:
                result = future.result()
                profiles.extend({**result, **profile} for profile in result.pop("profiles"))
            except Exception as exc:  # noqa: BLE001
                failed.append({"educationLevel": item["educationLevel"],
                               "majorClassCode": item["majorClassCode"], "error": str(exc)[:1000]})
            if completed % 5 == 0 or completed == len(class_manifest):
                print(json.dumps({"classProgress": completed, "totalClasses": len(class_manifest),
                                  "profiles": len(profiles), "failedClasses": len(failed)},
                                 ensure_ascii=False), flush=True)
    # 官网专业简介专栏公开 1346 项；2021 目录的职业本科另有 3 项无公开简介正文。
    public_expected = {"SECONDARY_VOCATIONAL": 358,
                       "HIGHER_VOCATIONAL_SPECIALIST": 744,
                       "VOCATIONAL_BACHELOR": 244}
    counts = {level: sum(x["educationLevel"] == level for x in profiles) for level in LEVELS}
    errors = {level: {"expected": expected, "actual": counts[level]}
              for level, expected in public_expected.items() if counts[level] != expected}
    if failed or errors:
        raise RuntimeError(f"专业简介数量门禁失败：{json.dumps({'counts': errors, 'failed': failed}, ensure_ascii=False)}")
    return sorted(profiles, key=lambda x: (x["educationLevel"], x["majorCode"])), failed


def apply_profiles(profiles: list[dict]) -> dict:
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(NationalStandardSource).where(
            NationalStandardSource.source_key == "MOE_PROFESSIONAL_PROFILE",
            NationalStandardSource.version_label == "2022",
            NationalStandardSource.is_deleted.is_(False))).first()
        if not source:
            source = NationalStandardSource(source_key="MOE_PROFESSIONAL_PROFILE",
                source_type="PROFESSIONAL_PROFILE", title="新版职业教育专业简介（1349个专业）",
                publisher="中华人民共和国教育部", version_label="2022", source_url=BASE_URL,
                published_date=date(2022, 9, 7), is_official=True,
                copyright_policy="INTERNAL_SEARCH_LINK_SOURCE", retrieval_status="RUNNING",
                item_count=len(profiles), metadata_json={})
            db.add(source); db.flush()
        source.item_count = len(profiles); source.retrieval_status = "RUNNING"
        source.last_crawled_at = datetime.now(UTC).replace(tzinfo=None)
        source.manifest_sha256 = hashlib.sha256(json.dumps(
            [{k: x[k] for k in ("educationLevel", "majorCode", "majorName", "sourceUrl")}
             for x in profiles], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        for item in profiles:
            major = db.scalars(select(NationalMajorCatalog).where(
                NationalMajorCatalog.catalog_version == "2021",
                NationalMajorCatalog.education_level == item["educationLevel"],
                NationalMajorCatalog.major_code == item["majorCode"],
                NationalMajorCatalog.is_deleted.is_(False))).first()
            metadata = {**(dict(major.metadata_json or {}) if major else {}),
                        "professionalProfileAvailable": True,
                        "standardCovered": bool(major and (major.metadata_json or {}).get("standardCovered"))}
            if not major:
                major = NationalMajorCatalog(source_id=source.id, catalog_version="2021",
                    education_level=item["educationLevel"], category_code=item["categoryCode"],
                    category_name=item["categoryName"], major_class_code=item["majorClassCode"],
                    major_class_name=item["majorClassName"], major_code=item["majorCode"],
                    major_name=item["majorName"], directory_status="ACTIVE",
                    effective_date=date(2021, 3, 12), metadata_json=metadata)
                db.add(major); db.flush()
            else:
                major.category_code = item["categoryCode"]
                major.category_name = item["categoryName"] or major.category_name
                major.major_class_code = item["majorClassCode"]
                major.major_class_name = item["majorClassName"]
                major.major_name = item["majorName"]; major.metadata_json = metadata
            standard_code = f"MOE-PROFILE-2022-{item['educationLevel']}-{item['majorCode']}"
            document = db.scalars(select(NationalStandardDocument).where(
                NationalStandardDocument.standard_code == standard_code,
                NationalStandardDocument.version_label == "2022",
                NationalStandardDocument.is_deleted.is_(False))).first()
            values = {"source_id": source.id, "major_catalog_id": major.id,
                      "document_type": "PROFESSIONAL_PROFILE",
                      "title": f"{item['majorName']}专业简介（{item['educationLevelName']}）",
                      "education_level": item["educationLevel"], "major_code": item["majorCode"],
                      "major_name": item["majorName"], "published_date": date(2022, 9, 7),
                      "source_url": item["sourceUrl"], "source_file_name": item["sourceFileName"],
                      "source_sha256": item["sourceSha256"], "page_count": item["pageCount"],
                      "text_status": item["textStatus"], "full_text": item["fullText"],
                      "structured_json": {"majorClassCode": item["majorClassCode"],
                                          "sectionCodes": [x["sectionCode"] for x in item["sections"]]},
                      "char_count": item["charCount"], "status": "PUBLISHED", "extraction_error": None}
            if not document:
                document = NationalStandardDocument(standard_code=standard_code, version_label="2022", **values)
                db.add(document); db.flush()
            else:
                for key, value in values.items():
                    setattr(document, key, value)
                document.version += 1; db.flush()
            active_codes = set()
            for row in item["sections"]:
                active_codes.add(row["sectionCode"])
                section = db.scalars(select(NationalStandardSection).where(
                    NationalStandardSection.document_id == document.id,
                    NationalStandardSection.section_code == row["sectionCode"])).first()
                if not section:
                    db.add(NationalStandardSection(document_id=document.id,
                        section_code=row["sectionCode"], section_no=row["sectionNo"],
                        section_title=row["sectionTitle"], content_text=row["content"],
                        content_sha256=row["contentSha256"]))
                else:
                    section.section_no = row["sectionNo"]; section.section_title = row["sectionTitle"]
                    section.content_text = row["content"]; section.content_sha256 = row["contentSha256"]
                    section.is_deleted = False; section.version += 1
            for old in db.scalars(select(NationalStandardSection).where(
                    NationalStandardSection.document_id == document.id,
                    NationalStandardSection.is_deleted.is_(False))).all():
                if old.section_code not in active_codes:
                    old.is_deleted = True; old.version += 1
        db.flush()
        stored = db.scalar(select(func.count(NationalStandardDocument.id)).where(
            NationalStandardDocument.source_id == source.id,
            NationalStandardDocument.document_type == "PROFESSIONAL_PROFILE",
            NationalStandardDocument.text_status.in_(("EXTRACTED", "METADATA_ONLY")),
            NationalStandardDocument.is_deleted.is_(False))) or 0
        full_text_count = db.scalar(select(func.count(NationalStandardDocument.id)).where(
            NationalStandardDocument.source_id == source.id,
            NationalStandardDocument.document_type == "PROFESSIONAL_PROFILE",
            NationalStandardDocument.text_status == "EXTRACTED",
            NationalStandardDocument.is_deleted.is_(False))) or 0
        source.retrieval_status = "COMPLETE" if stored == len(profiles) else "PARTIAL"
        source.metadata_json = {"officialCatalogCount": 1349, "publiclyAccessibleCount": 1346,
                                "officialPublicGap": 3, "stored": stored,
                                "fullTextCount": full_text_count,
                                "metadataOnlyCount": stored - full_text_count,
                                "levels": {level: sum(x["educationLevel"] == level for x in profiles)
                                           for level in LEVELS}}
        db.commit()
        return {"profiles": len(profiles), "stored": stored,
                "retrievalStatus": source.retrieval_status,
                "manifestSha256": source.manifest_sha256}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--manifest", type=Path, help="写出逐专业解析清单（包含正文，文件较大）")
    parser.add_argument("--manifest-input", type=Path, help="读取先前通过数量门禁的逐专业清单")
    args = parser.parse_args()
    if args.manifest_input:
        profiles = json.loads(args.manifest_input.read_text(encoding="utf-8"))
        counts = {level: sum(x["educationLevel"] == level for x in profiles) for level in LEVELS}
        public_expected = {"SECONDARY_VOCATIONAL": 358,
                           "HIGHER_VOCATIONAL_SPECIALIST": 744,
                           "VOCATIONAL_BACHELOR": 244}
        if any(counts[level] != expected for level, expected in public_expected.items()):
            raise RuntimeError(f"专业简介输入清单数量门禁失败：{counts}")
    else:
        profiles, _ = build_profile_manifest(crawl_class_manifest(), args.workers)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"profiles": len(profiles), "levels": {
        level: sum(x["educationLevel"] == level for x in profiles) for level in LEVELS}},
        ensure_ascii=False), flush=True)
    if args.apply:
        print(json.dumps(apply_profiles(profiles), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
