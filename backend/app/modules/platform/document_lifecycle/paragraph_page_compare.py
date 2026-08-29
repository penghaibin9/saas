"""Versioned directional paragraph/page comparison (not Office Track Changes)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import time

from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.safe_text_parser import ExtractedDocument, TextBlock

ALGORITHM_CODE = "PARAGRAPH_PAGE_V1"
ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class Change:
    status: str
    left: dict | None
    right: dict | None


@dataclass(frozen=True, slots=True)
class CompareArtifact:
    algorithm_code: str
    algorithm_version: str
    unchanged: int
    added: int
    removed: int
    modified: int
    changes: tuple[Change, ...]


def _view(block: TextBlock) -> dict:
    return asdict(block)


def compare_documents(left: ExtractedDocument, right: ExtractedDocument,
                      *, max_blocks: int = 10_000,
                      max_pair_product: int = 4_000_000,
                      max_characters: int = 4_000_000,
                      timeout_seconds: float = 15.0) -> CompareArtifact:
    if len(left.blocks) > max_blocks or len(right.blocks) > max_blocks:
        raise AppException("DOCUMENT_COMPARE_LIMIT", "文档段落数量超过比较上限", http_status=422)
    if len(left.blocks) * len(right.blocks) > max_pair_product:
        raise AppException("DOCUMENT_COMPARE_LIMIT", "文档比较复杂度超过安全上限", http_status=422)
    if left.character_count + right.character_count > max_characters:
        raise AppException("DOCUMENT_COMPARE_LIMIT", "文档比较字符量超过安全上限", http_status=422)
    if timeout_seconds <= 0:
        raise AppException("DOCUMENT_COMPARE_TIMEOUT", "文档比较超时", http_status=422)
    started = time.monotonic()
    matcher = SequenceMatcher(
        None,
        [item.normalized_sha256 for item in left.blocks],
        [item.normalized_sha256 for item in right.blocks],
        autojunk=False,
    )
    opcodes = matcher.get_opcodes()
    if time.monotonic() - started > timeout_seconds:
        raise AppException("DOCUMENT_COMPARE_TIMEOUT", "文档比较超时", http_status=422)
    changes: list[Change] = []
    counts = {"UNCHANGED": 0, "ADDED": 0, "REMOVED": 0, "MODIFIED": 0}
    for tag, i1, i2, j1, j2 in opcodes:
        if time.monotonic() - started > timeout_seconds:
            raise AppException("DOCUMENT_COMPARE_TIMEOUT", "文档比较超时", http_status=422)
        left_part = left.blocks[i1:i2]
        right_part = right.blocks[j1:j2]
        if tag == "equal":
            for before, after in zip(left_part, right_part):
                changes.append(Change("UNCHANGED", _view(before), _view(after)))
                counts["UNCHANGED"] += 1
        elif tag == "delete":
            for before in left_part:
                changes.append(Change("REMOVED", _view(before), None))
                counts["REMOVED"] += 1
        elif tag == "insert":
            for after in right_part:
                changes.append(Change("ADDED", None, _view(after)))
                counts["ADDED"] += 1
        else:
            paired = min(len(left_part), len(right_part))
            for index in range(paired):
                changes.append(Change("MODIFIED", _view(left_part[index]), _view(right_part[index])))
                counts["MODIFIED"] += 1
            for before in left_part[paired:]:
                changes.append(Change("REMOVED", _view(before), None))
                counts["REMOVED"] += 1
            for after in right_part[paired:]:
                changes.append(Change("ADDED", None, _view(after)))
                counts["ADDED"] += 1
    return CompareArtifact(
        algorithm_code=ALGORITHM_CODE,
        algorithm_version=ALGORITHM_VERSION,
        unchanged=counts["UNCHANGED"],
        added=counts["ADDED"],
        removed=counts["REMOVED"],
        modified=counts["MODIFIED"],
        changes=tuple(changes),
    )
