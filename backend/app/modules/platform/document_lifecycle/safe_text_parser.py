"""Bounded P0 text extraction for TXT, text-layer PDF and DOCX."""
from __future__ import annotations

import hashlib
import io
import re
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.etree import ElementTree

from pypdf import PdfReader

from app.core.exceptions import AppException

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass(frozen=True, slots=True)
class ParserBudgets:
    max_source_bytes: int = 20 * 1024 * 1024
    max_pages: int = 500
    max_characters: int = 2_000_000
    max_paragraphs: int = 100_000
    max_docx_entries: int = 2_000
    max_single_inflated_bytes: int = 20 * 1024 * 1024
    max_total_inflated_bytes: int = 100 * 1024 * 1024
    max_xml_part_bytes: int = 10 * 1024 * 1024
    timeout_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class TextBlock:
    page: int | None
    paragraph: int
    text: str
    normalized_sha256: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    source_kind: str
    page_count: int | None
    character_count: int
    blocks: tuple[TextBlock, ...]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "")).strip()


def _block(page: int | None, paragraph: int, text: str) -> TextBlock | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    return TextBlock(
        page=page,
        paragraph=paragraph,
        text=text.strip(),
        normalized_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _fail(message: str, *, code: str = "DOCUMENT_PARSE_REJECTED") -> AppException:
    return AppException(code, message, http_status=422)


def _check_time(started: float, budgets: ParserBudgets) -> None:
    if time.monotonic() - started > budgets.timeout_seconds:
        raise _fail("文档解析超时", code="DOCUMENT_PARSE_TIMEOUT")


def _finish(kind: str, page_count: int | None, blocks: list[TextBlock], budgets: ParserBudgets) -> ExtractedDocument:
    characters = sum(len(item.text) for item in blocks)
    if len(blocks) > budgets.max_paragraphs:
        raise _fail("文档段落数量超过安全上限")
    if characters > budgets.max_characters:
        raise _fail("文档字符数量超过安全上限")
    return ExtractedDocument(kind, page_count, characters, tuple(blocks))


def _append_bounded(blocks: list[TextBlock], item: TextBlock | None,
                    budgets: ParserBudgets, character_count: int) -> int:
    if item is None:
        return character_count
    if len(blocks) >= budgets.max_paragraphs:
        raise _fail("文档段落数量超过安全上限")
    next_count = character_count + len(item.text)
    if next_count > budgets.max_characters:
        raise _fail("文档字符数量超过安全上限")
    blocks.append(item)
    return next_count


def extract_text(data: bytes, *, ext: str | None, mime_type: str | None = None,
                 budgets: ParserBudgets | None = None) -> ExtractedDocument:
    limits = budgets or ParserBudgets()
    if not isinstance(data, bytes) or not data:
        raise _fail("文档内容为空")
    if len(data) > limits.max_source_bytes:
        raise _fail("源文件大小超过安全上限")
    suffix = str(ext or "").lower().lstrip(".")
    mime = str(mime_type or "").lower()
    started = time.monotonic()
    if suffix == "txt" or mime == "text/plain":
        return _extract_txt(data, limits, started)
    if suffix == "pdf" or mime == "application/pdf":
        return _extract_pdf(data, limits, started)
    if suffix == "docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx(data, limits, started)
    raise _fail("不支持的文档类型", code="DOCUMENT_TYPE_UNSUPPORTED")


def _extract_txt(data: bytes, budgets: ParserBudgets, started: float) -> ExtractedDocument:
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise _fail("TXT 必须是 UTF-8 编码") from exc
    blocks: list[TextBlock] = []
    characters = 0
    for paragraph, part in enumerate(re.split(r"(?:\r?\n){2,}", text), 1):
        _check_time(started, budgets)
        characters = _append_bounded(blocks, _block(None, paragraph, part), budgets, characters)
    return _finish("TXT", None, blocks, budgets)


def _extract_pdf(data: bytes, budgets: ParserBudgets, started: float) -> ExtractedDocument:
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise _fail("加密 PDF 不允许解析")
        if len(reader.pages) > budgets.max_pages:
            raise _fail("PDF 页数超过安全上限")
        blocks: list[TextBlock] = []
        paragraph = 0
        characters = 0
        for page_no, page in enumerate(reader.pages, 1):
            _check_time(started, budgets)
            page_text = page.extract_text() or ""
            _check_time(started, budgets)
            for part in re.split(r"(?:\r?\n){2,}", page_text):
                paragraph += 1
                item = _block(page_no, paragraph, part)
                characters = _append_bounded(blocks, item, budgets, characters)
    except AppException:
        raise
    except Exception as exc:
        raise _fail("PDF 结构损坏或不受支持") from exc
    if not blocks:
        raise _fail("PDF 没有可用文本层，需要 OCR", code="OCR_REQUIRED")
    return _finish("PDF_TEXT_LAYER", len(reader.pages), blocks, budgets)


def _unsafe_zip_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return normalized.startswith(("/", "\\")) or bool(path.parts and ":" in path.parts[0]) or ".." in path.parts


def _read_xml(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budgets: ParserBudgets) -> bytes:
    if info.file_size > budgets.max_xml_part_bytes:
        raise _fail("DOCX XML 部件超过安全上限")
    with archive.open(info, "r") as reader:
        raw = reader.read(budgets.max_xml_part_bytes + 1)
    if len(raw) > budgets.max_xml_part_bytes:
        raise _fail("DOCX XML 部件超过安全上限")
    lowered = raw.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise _fail("DOCX 禁止 DTD/ENTITY")
    return raw


def _extract_docx(data: bytes, budgets: ParserBudgets, started: float) -> ExtractedDocument:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > budgets.max_docx_entries:
                raise _fail("DOCX 条目数量超过安全上限")
            total = 0
            by_name = {}
            for info in infos:
                _check_time(started, budgets)
                if _unsafe_zip_name(info.filename):
                    raise _fail("DOCX 包含路径穿越条目")
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise _fail("DOCX 禁止符号链接条目")
                normalized_name = info.filename.replace("\\", "/")
                if normalized_name in by_name:
                    raise _fail("DOCX 包含重复条目")
                if info.file_size > budgets.max_single_inflated_bytes:
                    raise _fail("DOCX 单个解压条目超过安全上限")
                total += info.file_size
                if total > budgets.max_total_inflated_bytes:
                    raise _fail("DOCX 解压总量超过安全上限")
                by_name[normalized_name] = info

            for name, info in by_name.items():
                if name.endswith(".rels"):
                    root = ElementTree.fromstring(_read_xml(archive, info, budgets))
                    _check_time(started, budgets)
                    for rel in root.findall(f"{_REL_NS}Relationship"):
                        target = str(rel.attrib.get("Target") or "")
                        if str(rel.attrib.get("TargetMode") or "").upper() == "EXTERNAL" \
                                or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
                            raise _fail("DOCX 禁止外部关系")

            document = by_name.get("word/document.xml")
            if document is None:
                raise _fail("DOCX 缺少 word/document.xml")
            root = ElementTree.fromstring(_read_xml(archive, document, budgets))
            _check_time(started, budgets)
            blocks: list[TextBlock] = []
            characters = 0
            for paragraph, node in enumerate(root.iter(f"{_WORD_NS}p"), 1):
                _check_time(started, budgets)
                text = "".join(item.text or "" for item in node.iter(f"{_WORD_NS}t"))
                item = _block(None, paragraph, text)
                characters = _append_bounded(blocks, item, budgets, characters)
    except AppException:
        raise
    except (zipfile.BadZipFile, ElementTree.ParseError, RuntimeError) as exc:
        raise _fail("DOCX 结构损坏或不受支持") from exc
    return _finish("DOCX", None, blocks, budgets)
