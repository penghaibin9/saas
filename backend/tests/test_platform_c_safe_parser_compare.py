from __future__ import annotations

import io
import zipfile

import pytest
from pypdf import PdfWriter

from app.core.exceptions import AppException
from app.modules.platform.document_lifecycle.paragraph_page_compare import compare_documents
from app.modules.platform.document_lifecycle.safe_text_parser import ParserBudgets, extract_text


def _docx(document_xml: bytes, *, relationship_xml: bytes | None = None,
          extra: tuple[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
        if relationship_xml is not None:
            archive.writestr("word/_rels/document.xml.rels", relationship_xml)
        if extra is not None:
            archive.writestr(*extra)
    return buf.getvalue()


def test_txt_extracts_bounded_normalized_paragraphs() -> None:
    result = extract_text("第一段\n\n第二  段".encode(), ext="txt")
    assert [item.text for item in result.blocks] == ["第一段", "第二  段"]
    assert result.blocks[1].normalized_sha256 != result.blocks[0].normalized_sha256


def test_docx_extracts_paragraphs_without_inventing_page_numbers() -> None:
    xml = b'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Alpha</w:t></w:r></w:p><w:p><w:r><w:t>Beta</w:t></w:r></w:p></w:body></w:document>'''
    result = extract_text(_docx(xml), ext="docx")
    assert [item.text for item in result.blocks] == ["Alpha", "Beta"]
    assert all(item.page is None for item in result.blocks)


@pytest.mark.parametrize(
    "payload",
    [
        _docx(b'<!DOCTYPE x [<!ENTITY y "boom">]><x>&y;</x>'),
        _docx(b'<x/>', extra=("../escape.xml", b"x")),
        _docx(
            b'<x/>',
            relationship_xml=b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" TargetMode="External" Target="https://evil.invalid/x"/></Relationships>''',
        ),
    ],
)
def test_docx_rejects_dtd_traversal_and_external_relationships(payload: bytes) -> None:
    with pytest.raises(AppException) as exc:
        extract_text(payload, ext="docx")
    assert exc.value.code == "DOCUMENT_PARSE_REJECTED"


def test_docx_rejects_inflated_entry_budget() -> None:
    xml = b'<x>' + b'a' * 100 + b'</x>'
    with pytest.raises(AppException):
        extract_text(_docx(xml), ext="docx", budgets=ParserBudgets(max_single_inflated_bytes=20))


def test_scanned_pdf_is_not_reported_as_empty_success() -> None:
    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buf)
    with pytest.raises(AppException) as exc:
        extract_text(buf.getvalue(), ext="pdf")
    assert exc.value.code == "OCR_REQUIRED"


def test_compare_preserves_direction_and_four_status_contract() -> None:
    left = extract_text(b"same\n\nold\n\nremove", ext="txt")
    right = extract_text(b"same\n\nnew\n\nadd\n\nextra", ext="txt")
    forward = compare_documents(left, right)
    reverse = compare_documents(right, left)
    assert forward.algorithm_code == "PARAGRAPH_PAGE_V1"
    assert forward.unchanged == 1
    assert forward.modified == 2
    assert forward.added == 1
    assert reverse.removed == 1
    assert forward.changes != reverse.changes
