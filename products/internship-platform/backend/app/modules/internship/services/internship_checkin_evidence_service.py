"""C02 trusted check-in photo evidence.

The original upload stays immutable.  The server derives a second JPEG containing the
server-local timestamp and submitted location text, stores both SHA-256 digests and binds
both files to the check-in business object.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.config import settings
from app.core.exceptions import AppException
from app.services import file_service

_COMMON_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)


def _font(size: int, text: str):
    candidates = [settings.CHECKIN_WATERMARK_FONT_PATH, *_COMMON_FONTS]
    for raw in candidates:
        path = str(raw or "").strip()
        if not path or not Path(path).exists():
            continue
        try:
            font = ImageFont.truetype(path, size=size)
            # Force glyph layout now so a configured-but-incompatible font fails here.
            ImageDraw.Draw(Image.new("RGB", (8, 8))).textbbox((0, 0), text, font=font)
            return font
        except Exception:
            continue
    if all(ord(ch) < 128 for ch in text):
        return ImageFont.load_default()
    raise AppException(
        "CHECKIN_WATERMARK_FONT_MISSING",
        "服务器缺少可渲染中文地址的水印字体，已拒绝生成不完整水印",
        http_status=503,
    )


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines = []
    current = ""
    for ch in str(text or ""):
        candidate = current + ch
        if current and draw.textbbox((0, 0), candidate, font=font)[2] > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or ["-"]


def watermark_photo(*, original_file_id: str, checkin_id: int, watermark_text: str,
                    actor: dict, db) -> dict:
    meta = file_service.get_file_meta(original_file_id, actor)
    if not meta:
        raise AppException("VALIDATION_ERROR", "现场照片不存在")
    mime = str(meta.get("mimeType") or "").lower()
    if not mime.startswith("image/"):
        raise AppException("VALIDATION_ERROR", "签到现场凭证必须是图片")

    resolved = file_service.resolve_download(original_file_id, user=actor)
    if not resolved:
        raise AppException("FILE_NOT_READY", "现场照片尚未安全就绪", http_status=409)
    source_path, source_name = resolved
    try:
        with Image.open(source_path) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
    except Exception as exc:
        raise AppException("VALIDATION_ERROR", "现场照片无法解码，请重新拍摄") from exc

    width, height = image.size
    if width < 160 or height < 160:
        raise AppException("VALIDATION_ERROR", "现场照片尺寸过小，请重新拍摄")

    font_size = max(18, min(42, width // 28))
    font = _font(font_size, watermark_text)
    draw = ImageDraw.Draw(image, "RGBA")
    padding = max(12, width // 80)
    lines = _wrap(draw, watermark_text, font, max_width=width - padding * 2)
    line_height = int(font_size * 1.45)
    panel_height = padding * 2 + line_height * len(lines)
    top = max(0, height - panel_height)
    draw.rectangle((0, top, width, height), fill=(0, 0, 0, 150))
    y = top + padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=(255, 255, 255, 245))
        y += line_height

    out = BytesIO()
    image.save(out, format="JPEG", quality=90, optimize=True)
    result = file_service.store_bytes(
        out.getvalue(),
        f"checkin-{checkin_id}-watermarked.jpg",
        biz_type="INTERNSHIP_CHECKIN",
        mime_type="image/jpeg",
        biz_id=checkin_id,
        user=actor,
        visibility="BIZ_SCOPED",
        db=db,
    )
    file_service.bind_file_biz(
        original_file_id, "INTERNSHIP_CHECKIN", checkin_id, user=actor, db=db
    )
    return {
        "originalFileId": str(original_file_id),
        "originalSha256": str(meta.get("sha256") or ""),
        "watermarkedFileId": str(result["fileId"]),
        "watermarkedSha256": str(result.get("sha256") or ""),
        "originalFileName": str(source_name or meta.get("fileName") or ""),
    }
