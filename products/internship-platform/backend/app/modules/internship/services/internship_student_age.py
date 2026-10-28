"""Shared age authority; never expose identity plaintext in API results."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.config import settings
from app.core.exceptions import AppException
from app.core.field_crypto import decrypt_sensitive

MINIMUM_AGE_CHECK_CODE = "minimumAge"

def policy_today() -> date:
    return (datetime.utcnow() + timedelta(hours=settings.TIMEZONE_OFFSET_HOURS)).date()


_RESIDENT_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_RESIDENT_ID_CHECK_CODES = "10X98765432"


def student_birth_date(student, *, today=None, decryptor=None) -> date | None:
    """Return a verified birth date without exposing the stored identity number.

    Some deployments may add a dedicated ``birth_date`` column. The current
    student master stores only an encrypted resident ID, so use that as the
    authoritative fallback. Missing/corrupt ciphertext and malformed IDs stay
    unknown so the guardian-consent gate remains fail-closed.
    """
    today = today or policy_today()
    if student is None:
        return None
    direct = getattr(student, "birth_date", None)
    if isinstance(direct, datetime):
        direct = direct.date()
    if isinstance(direct, date):
        return direct if direct <= today else None

    stored = getattr(student, "id_card_encrypted", None)
    if not stored:
        return None
    try:
        plain = (decryptor or decrypt_sensitive)(stored, "id_card")
    except Exception:  # decryption failure must not bypass guardian consent
        return None
    text = str(plain or "").strip().upper()
    if not text.isascii():
        return None
    if len(text) == 18:
        if not text[:17].isdigit() or text[-1] not in "0123456789X":
            return None
        expected = _RESIDENT_ID_CHECK_CODES[
            sum(int(number) * weight for number, weight in zip(text[:17], _RESIDENT_ID_WEIGHTS)) % 11
        ]
        if text[-1] != expected:
            return None
        birth_text = text[6:14]
    elif len(text) == 15 and text.isdigit():
        birth_text = f"19{text[6:12]}"
    else:
        return None
    try:
        birth = datetime.strptime(birth_text, "%Y%m%d").date()
    except ValueError:
        return None
    return birth if birth <= today else None



def has_reached_age(birth: date, years: int, *, today=None) -> bool:
    today = today or policy_today()
    try:
        birthday = birth.replace(year=birth.year + years)
    except ValueError:
        birthday = birth.replace(year=birth.year + years, day=28)
    return today >= birthday


def student_age_years(student, *, today=None) -> int | None:
    today = today or policy_today()
    birth = student_birth_date(student, today=today)
    if birth is None:
        return None
    years = today.year - birth.year
    return years if has_reached_age(birth, years, today=today) else years - 1


def placement_age_date(record=None, batch=None, *, today=None) -> date:
    """Do not age up historical placements, or use future plans to bypass today's gate."""
    today = today or policy_today()
    # A late-joining student must not be judged at the cohort start date.
    # Only the actual record start can establish a historical placement.
    raw = getattr(record, "intern_start_date", None)
    if isinstance(raw, datetime):
        raw = raw.date()
    if isinstance(raw, str):
        try:
            raw = date.fromisoformat(raw[:10])
        except ValueError:
            raw = None
    return min(today, raw) if isinstance(raw, date) else today


def minimum_age_item(student, *, record=None, batch=None, today=None) -> dict:
    """Unconditional gate, separate from guardian consent and work-rights exemptions."""
    today = today or policy_today()
    birth = student_birth_date(student, today=today)
    reference = placement_age_date(record, batch, today=today)
    if birth is None or birth > reference:
        status, reason = "PENDING", "出生日期待学校核实，暂不能安排岗位实习；实习年龄不得豁免"
    elif not has_reached_age(birth, 16, today=reference):
        status, reason = "REJECTED", "未满16周岁不得安排岗位实习；监护人同意、特殊备案和合规豁免均不能替代年龄条件"
    else:
        status, reason = "VALID", ""
    return {
        "code": MINIMUM_AGE_CHECK_CODE, "label": "岗位实习年龄（满16周岁）",
        "required": True, "applicable": True, "severity": "BLOCK",
        "status": status, "reason": reason, "exemptible": False,
        "evidenceId": None, "evidenceVersion": None, "route": "",
    }


def is_non_exemptible_check(check_code) -> bool:
    return str(check_code or "").strip().casefold() == MINIMUM_AGE_CHECK_CODE.casefold()


def assert_exemption_allowed(check_code) -> None:
    if is_non_exemptible_check(check_code):
        raise AppException("VALIDATION_ERROR", "岗位实习年龄属于不可豁免的硬性门禁，请先由学校核实学生主档")
