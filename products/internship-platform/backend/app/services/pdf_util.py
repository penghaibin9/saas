"""PDF 套打通用工具（reportlab + STSong-Light，支持中文正文与水印）。"""
from __future__ import annotations

import base64
import io
from datetime import datetime

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def _ensure_cjk_font() -> str:
    name = "STSong-Light"
    try:
        pdfmetrics.getFont(name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_text_pdf(title: str, body: str, watermark: str = "") -> bytes:
    """生成带标题、正文与水印的单页或多页 PDF。"""
    font = _ensure_cjk_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=(title or "文档")[:120],
    )
    title_style = ParagraphStyle(
        "PdfTitle", fontName=font, fontSize=16, leading=22, alignment=TA_LEFT, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "PdfBody", fontName=font, fontSize=11, leading=18, alignment=TA_LEFT, spaceAfter=6,
    )
    wm_style = ParagraphStyle(
        "PdfWm", fontName=font, fontSize=8, leading=10, textColor="#888888", alignment=TA_LEFT,
    )
    story = []
    if watermark:
        story.append(Paragraph(_escape(watermark), wm_style))
        story.append(Spacer(1, 6))
    if title:
        story.append(Paragraph(_escape(title), title_style))
        story.append(Spacer(1, 8))
    for para in (body or "").split("\n"):
        line = para.strip()
        if line:
            story.append(Paragraph(_escape(line), body_style))
        else:
            story.append(Spacer(1, 6))
    doc.build(story)
    return buf.getvalue()


def pack_pdf_result(content: bytes, filename: str, tenant_label: str = "") -> dict:
    """API 响应：PDF 二进制转 base64，文件名补时间戳。"""
    name = filename if filename.endswith(".pdf") else f"{filename}.pdf"
    if not any(c.isdigit() for c in name[-20:]):
        stem = name[:-4] if name.endswith(".pdf") else name
        suffix = f"_{tenant_label}" if tenant_label else ""
        name = f"{stem}{suffix}_{datetime.now():%Y%m%d_%H%M}.pdf"
    return {
        "filename": name,
        "contentBase64": base64.b64encode(content).decode("ascii"),
        "mediaType": "application/pdf",
    }
