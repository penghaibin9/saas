"""Bounded, inert ZIP ingestion. Never extract paths to disk or fetch source URLs.

JSON + UTF-8 Markdown + re-encoded raster pictures are accepted. Limits protect
resources, not daily publication volume. No manifest value can approve a draft.
"""
from __future__ import annotations
import hashlib
import io
import ipaddress
import json
import re
import stat
import unicodedata
import warnings
import zipfile
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import urlsplit, urlunsplit

SCHEMA = "yueke.news-package/1"
MAX_ARCHIVE = 25 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
MAX_FILES = 5000
MAX_ARTICLES = 2000  # Per-upload resource ceiling; never a daily publishing cap.
CATEGORIES = {
    "academic": "教务管理", "affairs": "学生工作", "internship": "岗位实习",
    "graduation": "毕业设计", "hr": "高校人事", "policy": "教育政策",
    "technology": "教育科技", "company": "跃科动态",
}
KEYWORDS = {
    "internship": ("实习", "校企", "产教", "就业"),
    "graduation": ("毕业设计", "毕业论文", "答辩", "选题"),
    "hr": ("人事", "职称", "教师发展", "招聘", "师资", "薪酬"),
    "affairs": ("学工", "学生工作", "资助", "辅导员", "宿舍", "心理"),
    "academic": ("教务", "排课", "选课", "考务", "学籍", "课程", "学分"),
    "policy": ("政策", "教育部", "通知", "办法", "意见"),
    "technology": ("人工智能", "数字", "AI", "技术", "软件"),
}

class PackageError(ValueError):
    pass

def digest(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf8") if isinstance(value, str) else value).hexdigest()

def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackageError("JSON 字段重复：" + key)
        result[key] = value
    return result

def load_json(data: bytes):
    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PackageError("资源包 JSON 格式错误或嵌套过深") from exc

def safe_path(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 240:
        raise PackageError("无效文件名")
    if any(ord(c) < 32 for c in name) or any(c in name for c in "\\:%"):
        raise PackageError("不允许的文件路径")
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in (".", "..", "") for p in name.split("/")):
        raise PackageError("不允许的文件路径")
    if str(path) != name:
        raise PackageError("不规范的文件路径")
    return name

def public_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 1800 or any(ord(c) <= 32 for c in value):
        raise PackageError("来源链接格式错误")
    try:
        p = urlsplit(value)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            raise ValueError()
        if p.port not in (None, 80, 443) or "." not in p.hostname or "\\" in value:
            raise ValueError()
        host = p.hostname.lower().rstrip(".")
        if host.endswith((".local", ".internal", ".localhost", ".test", ".invalid")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
        return urlunsplit((p.scheme, p.netloc.lower(), p.path or "/", p.query, ""))
    except ValueError as exc:
        raise PackageError("来源必须是公开 HTTP/HTTPS 链接") from exc

def classify(title: str, summary: str, explicit=None) -> str:
    if explicit is not None and not isinstance(explicit, str):
        raise PackageError("分类须为文字")
    if explicit in CATEGORIES:
        return explicit
    for key, label in CATEGORIES.items():
        if explicit == label:
            return key
    text = title + " " + summary
    scores = {key: sum(text.count(term) for term in words) for key, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "technology"

def _text(value, label, lo, hi):
    if not isinstance(value, str) or not lo <= len(value.strip()) <= hi:
        raise PackageError(f"{label}需要 {lo}—{hi} 个字符")
    value = value.strip()
    if "\x00" in value:
        raise PackageError(label + "包含非法字符")
    return value

def _picture(data: bytes):
    from PIL import Image, UnidentifiedImageError
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ("PNG", "JPEG", "WEBP") or getattr(image, "n_frames", 1) != 1:
                    raise PackageError("只允许静态 PNG/JPEG/WebP 图片")
                if image.width * image.height > 16_000_000 or max(image.size) > 8000:
                    raise PackageError("图片像素过大")
                image.load()
                clean = image.convert("RGB")
                clean.thumbnail((2000, 2000))
                out = io.BytesIO()
                clean.save(out, format="WEBP", quality=86, method=3)
                result = out.getvalue()
                if len(result) > 4_000_000:
                    raise PackageError("图片处理后过大")
                return result, "image/webp"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise PackageError("图片损坏、类型不符或尺寸不安全") from exc

def parse_package(blob: bytes) -> dict:
    if not blob or len(blob) > MAX_ARCHIVE:
        raise PackageError("请上传不超过 25MB 的 ZIP；更大的内容可拆成多个包，发布不设每日条数上限")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except (zipfile.BadZipFile, OSError) as exc:
        raise PackageError("文件不是有效 ZIP") from exc
    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES:
            raise PackageError("包内文件过多，请拆成多个包上传")
        names, folded, total = {}, set(), 0
        for info in entries:
            name = safe_path(info.filename.rstrip("/") if info.is_dir() else info.filename)
            key = unicodedata.normalize("NFKC", name).casefold()
            if key in folded:
                raise PackageError("ZIP 包内存在重名或混淆路径")
            folded.add(key)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise PackageError("不允许链接或设备文件")
            if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise PackageError("不允许加密或不支持的压缩格式")
            if info.is_dir():
                continue
            if not (name == "manifest.json" or name == "README.md" or
                    name.startswith("articles/") and name.endswith(".md") or
                    name.startswith("assets/") and PurePosixPath(name).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")):
                raise PackageError("不支持的文件：" + name)
            limit = 4_000_000 if name.startswith("assets/") or name == "manifest.json" else 120_000
            if info.file_size > limit or info.file_size / max(info.compress_size, 1) > 150:
                raise PackageError("文件过大或压缩倍率异常")
            total += info.file_size
            if total > MAX_EXPANDED:
                raise PackageError("解压总量超过安全上限，请拆包")
            names[name] = info
        def read(name):
            if name not in names:
                raise PackageError("缺少文件：" + name)
            info = names[name]
            try:
                with archive.open(info) as member:
                    data = member.read(info.file_size + 1)
                if len(data) != info.file_size:
                    raise PackageError("ZIP 实际大小与清单不符")
                return data
            except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
                raise PackageError("ZIP 文件校验失败") from exc
        manifest = load_json(read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
            raise PackageError("资源包版本不支持，请使用系统提供的 GPT 新闻包格式")
        title = _text(manifest.get("title"), "资源包标题", 2, 200)
        article_meta = manifest.get("articles")
        if not isinstance(article_meta, list) or not 1 <= len(article_meta) <= MAX_ARTICLES:
            raise PackageError("单个 ZIP 需含 1—2000 篇文章；超出请拆包，不是每日发布限制")
        assets, media_errors = {}, {}
        for name in names:
            if name.startswith("assets/"):
                try:
                    picture, mime = _picture(read(name))
                    assets[name] = {"id": digest(picture), "content": picture, "mime": mime}
                except PackageError as exc:
                    media_errors[name] = str(exc)
        rows = []
        for ordinal, meta in enumerate(article_meta, 1):
            row = {"ordinal": ordinal, "title": f"第 {ordinal} 篇（待修复）", "summary": "", "body": "",
                   "category": "technology", "state": "INVALID", "issue": "", "sources": [],
                   "media_map": {}, "cover_id": None, "ai_assisted": True, "content_kind": "summary", "dedupe_key": None}
            try:
                if not isinstance(meta, dict):
                    raise PackageError("文章清单必须是对象")
                row["title"] = _text(meta.get("title"), "标题", 4, 240)
                row["summary"] = _text(meta.get("summary"), "摘要", 20, 600)
                row["category"] = classify(row["title"], row["summary"], meta.get("category"))
                path = safe_path(meta.get("file"))
                if not path.startswith("articles/") or not path.endswith(".md"):
                    raise PackageError("正文须放在 articles/ 下的 Markdown 文件")
                raw = read(path)
                if meta.get("sha256") and meta["sha256"] != digest(raw):
                    raise PackageError("正文 SHA256 与清单不符")
                try:
                    row["body"] = _text(raw.decode("utf-8-sig"), "正文", 120, 50_000)
                except UnicodeError as exc:
                    raise PackageError("正文须为 UTF-8 编码") from exc
                if re.search(r"<\s*(?:script|iframe|object|embed|style|form)\b", row["body"], re.I):
                    raise PackageError("正文包含不允许的活动内容")
                sources = meta.get("sources")
                if not isinstance(sources, list) or not 1 <= len(sources) <= 12:
                    raise PackageError("每篇新闻需有 1—12 个可核验来源，不能只填 AI 生成")
                for source in sources:
                    if not isinstance(source, dict):
                        raise PackageError("来源格式错误")
                    s = {"title": _text(source.get("title"), "来源名称", 2, 240), "url": public_url(source.get("url"))}
                    if source.get("published_at"):
                        try:
                            when = datetime.fromisoformat(source["published_at"].replace("Z", "+00:00"))
                        except (ValueError, TypeError, AttributeError) as exc:
                            raise PackageError("来源日期须为 ISO 日期") from exc
                        s["published_at"] = when.isoformat()
                    row["sources"].append(s)
                kind = meta.get("content_kind", "summary")
                if kind not in ("summary", "original", "product-update"):
                    raise PackageError("仅支持原创、来源摘要与产品更新，不导入未经授权的全文转载")
                row["content_kind"] = kind
                if "ai_assisted" in meta and not isinstance(meta["ai_assisted"], bool):
                    raise PackageError("ai_assisted 必须为布尔值")
                row["ai_assisted"] = meta.get("ai_assisted", True)
                used = set(re.findall(r"!\[[^\]\n]*\]\(([^)\s]+)\)", row["body"]))
                if meta.get("cover"):
                    used.add(safe_path(meta["cover"]))
                for name in used:
                    safe_path(name)
                    if name not in assets:
                        raise PackageError(media_errors.get(name, "配图缺失或不支持外链图片：" + name))
                    row["media_map"][name] = assets[name]["id"]
                if meta.get("cover"):
                    row["cover_id"] = assets[meta["cover"]]["id"]
                normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", row["body"]).casefold())
                row["dedupe_key"] = digest(normalized)
                row["state"] = "READY"
            except PackageError as exc:
                row["issue"] = str(exc)[:1000]
                row["dedupe_key"] = None
            rows.append(row)
        return {"sha256": digest(blob), "title": title, "articles": rows, "assets": assets,
                "review_digest": digest(canonical([{k: v for k, v in r.items()} for r in rows]))}
