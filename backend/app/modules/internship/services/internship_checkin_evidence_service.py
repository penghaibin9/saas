"""C02 trusted check-in photo evidence.

The original upload stays immutable.  The server derives a second JPEG containing the
server-local timestamp and submitted location text, stores both SHA-256 digests and binds
both files to the check-in business object.
"""
from __future__ import annotations

from io import BytesIO
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.exceptions import AppException
from app.services import file_access_service, file_business_binding_service, file_service

STUDENT_EVIDENCE_TYPES = frozenset({'INTERNSHIP_CHECKIN', 'INTERNSHIP_CHECKIN_EXEMPTION'})


def authorize_student_evidence(db, file_obj, bindings, user: dict, action: str) -> bool:
    """Authorize against the current business record, before any uploader fallback."""
    from app.core.context import current_tenant_id
    from app.core.permissions import has_permission
    from app.models import InternshipCheckin, InternshipCheckinExemption, InternshipRecord
    from app.modules.internship.services.internship_scope import assert_internship_record_scope

    if db is None or action not in {'meta', 'download', 'preview', 'archive'}:
        return False
    tenant_id = int(current_tenant_id() or 0)
    kind = str(file_obj.biz_type or '').upper()
    if kind not in STUDENT_EVIDENCE_TYPES or file_obj.tenant_id != tenant_id:
        return False
    fid = str(file_obj.id)
    if kind == 'INTERNSHIP_CHECKIN':
        model = InternshipCheckin
        predicate = or_(model.evidence_file_id == fid, model.watermarked_file_id == fid)
    else:
        model = InternshipCheckinExemption
        predicate = model.evidence_file_id == fid
    business = db.scalar(select(model).where(model.tenant_id == tenant_id,
        model.is_deleted.is_(False), predicate).limit(1))
    if not business or str(file_obj.biz_id) != str(business.id):
        return False
    if not any(binding.tenant_id == tenant_id and not binding.is_deleted
               and binding.status == 'ACTIVE' and binding.is_current
               and binding.biz_type == kind and str(binding.biz_id) == str(business.id)
               for binding in bindings):
        return False
    record = db.scalar(select(InternshipRecord).where(InternshipRecord.tenant_id == tenant_id,
        InternshipRecord.id == business.internship_id, InternshipRecord.is_deleted.is_(False)))
    if not record:
        return False
    if kind == 'INTERNSHIP_CHECKIN_EXEMPTION' and (
            record.student_id != business.student_id or record.batch_id != business.batch_id):
        return False
    if kind == 'INTERNSHIP_CHECKIN':
        digest = business.evidence_sha256 if fid == business.evidence_file_id else business.watermarked_sha256
        if not digest or digest != file_obj.sha256:
            return False
    if str(user.get('userType') or '').upper() == 'STUDENT':
        from app.services.mobile_student_service import resolve_student
        student = resolve_student(db, user)
        return bool(student and student.id == record.student_id)
    if not has_permission(user, 'internship.attendance.view'):
        return False
    assert_internship_record_scope(db, record.id, user, '查看签到佐证材料')
    return True

_CJK_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
)
_ASCII_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _font(size: int, text: str):
    non_ascii = any(ord(ch) >= 128 for ch in str(text or ""))
    candidates = [settings.CHECKIN_WATERMARK_FONT_PATH]
    candidates.extend(_CJK_FONTS if non_ascii else (*_CJK_FONTS, *_ASCII_FONTS))
    for raw in candidates:
        path = str(raw or "").strip()
        if not path or not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    if not non_ascii:
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
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
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
                    actor: dict, student_id: int | None = None, batch_id: str | None = None,
                    subject_type: str = "STUDENT", subject_id=None,
                    biz_type: str = "INTERNSHIP_CHECKIN", db) -> dict:
    file_obj = file_access_service.require_file_access(
        original_file_id, user=actor, action="bind"
    )
    meta = {
        "fileId": str(file_obj.id),
        "fileName": file_obj.file_name or "",
        "mimeType": file_obj.mime_type or "",
        "sha256": file_obj.sha256 or "",
    }
    mime = str(meta.get("mimeType") or "").lower()
    if not mime.startswith("image/"):
        raise AppException("VALIDATION_ERROR", "签到现场凭证必须是图片")

    resolved = file_service.resolve_download(original_file_id, user=actor)
    if not resolved:
        raise AppException("FILE_NOT_READY", "现场照片尚未安全就绪", http_status=409)
    source_path, source_name = resolved
    from app.services.internship_file_transfer_service import MAX_UPLOAD_BYTES
    try:
        with source_path.open('rb') as source:
            original_bytes = source.read(MAX_UPLOAD_BYTES + 1)
    except OSError as exc:
        raise AppException('FILE_NOT_READY', '现场照片暂时无法读取，请重新核验材料', http_status=409) from exc
    if (len(original_bytes) > MAX_UPLOAD_BYTES or len(original_bytes) != file_obj.size_bytes
            or not file_obj.sha256 or sha256(original_bytes).hexdigest() != file_obj.sha256):
        raise AppException('FILE_INTEGRITY_ERROR', '现场照片完整性校验失败，请重新上传原图', http_status=409)
    try:
        # Decode the exact bytes just verified, so the watermark and recorded
        # original digest cannot refer to different versions of a stored file.
        with Image.open(BytesIO(original_bytes)) as raw:
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
    if panel_height > height // 3:
        # Keep the full scene and all location text visible when an overlay would
        # cover the photograph or clip a long address on a small camera image.
        expanded = Image.new('RGB', (width, height + panel_height), (20, 24, 30))
        expanded.paste(image, (0, 0))
        image = expanded
        draw = ImageDraw.Draw(image, 'RGBA')
        top = height
    else:
        top = height - panel_height
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
        biz_type=biz_type,
        mime_type="image/jpeg",
        biz_id=checkin_id,
        user=actor,
        visibility="BIZ_SCOPED",
        db=db,
    )
    subject = str(subject_type or "STUDENT").upper()
    resolved_subject_id = subject_id if subject_id not in (None, "") else student_id
    if resolved_subject_id in (None, ""):
        raise AppException("VALIDATION_ERROR", "签到凭证缺少业务主体")
    scope = {"batchId": str(batch_id or "")}
    if subject == "STUDENT":
        scope["studentId"] = str(resolved_subject_id)
    elif subject == "TEACHER":
        scope["teacherUserId"] = str(resolved_subject_id)
    file_business_binding_service.bind_file_to_business(
        db,
        file_id=original_file_id,
        biz_type=biz_type,
        biz_id=checkin_id,
        actor=actor,
        subject_type=subject,
        subject_id=resolved_subject_id,
        relation_type="BUSINESS_EVIDENCE",
        module_code="INTERNSHIP",
        student_id=int(resolved_subject_id) if subject == "STUDENT" else None,
        batch_id=str(batch_id or "") or None,
        scope=scope,
    )
    return {
        "originalFileId": str(original_file_id),
        "originalSha256": str(meta.get("sha256") or ""),
        "watermarkedFileId": str(result["fileId"]),
        "watermarkedSha256": str(result.get("sha256") or ""),
        "originalFileName": str(source_name or meta.get("fileName") or ""),
    }
