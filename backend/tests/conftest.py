"""pytest å…¬å…±å¤¹å…·ï¼šå¼ºåˆ¶éš”ç¦»ç”Ÿäº§ MySQLï¼Œé»˜è®¤ mock æ¨¡å¼ï¼ˆä¸è¯»å†™ saas_lifecycleï¼‰ã€‚"""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

# å¿…é¡»åœ¨ import app ä¹‹å‰è¦†ç›–ï¼ˆé˜²æ­¢ shell `export $(grep .env)` æŠŠ DB_ENABLED=true å¸¦è¿› pytestï¼‰
os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "false"
os.environ["DATABASE_URL"] = ""
# æµ‹è¯•å¥—ä»¶åœ¨ç‹¬ç«‹æµ‹è¯•åº“é‡Œè‡ªå»ºç§Ÿæˆ·ï¼Œçº¦å®šä¸»ç§Ÿæˆ· = demo(MAIN_TENANT_ID 1000000000000000001)ï¼Œ
# ä¸Žç”Ÿäº§åº“é‡Œçš„çœŸå®žç§Ÿæˆ·æ— å…³ã€‚ç”Ÿäº§é»˜è®¤ç§Ÿæˆ·å·²äºŽ 2026-07-28 æ”¶æ•›ä¸º sandbox-schoolï¼Œæ•…æ­¤å¤„
# å¿…é¡»æ˜¾å¼é’‰ä½æµ‹è¯•è‡ªå·±çš„ç§Ÿæˆ·çº¦å®šï¼Œå¦åˆ™ mock-login ä¼šè§£æžåˆ°æ²™ç®±ç§Ÿæˆ·è€Œä¸Žå¤¹å…·æ•°æ®è·¨ç§Ÿæˆ·ä¸å¯è§ã€‚
os.environ["DEFAULT_TENANT_CODE"] = "demo"
# MySQL-only æ”¶å£ï¼šä¼˜å…ˆä½¿ç”¨æ˜¾å¼ TEST_DATABASE_URLã€‚
# è‹¥è¿›ç¨‹çŽ¯å¢ƒæœªæä¾›ï¼Œåˆ™å…œåº•è¯»å– backend/.env ä¸­çš„ TEST_DATABASE_URLï¼Œé¿å…æ‹¼å‡º saas_user:@...ã€‚
if "TEST_DATABASE_URL" not in os.environ:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TEST_DATABASE_URL" and v.strip():
                os.environ["TEST_DATABASE_URL"] = v.strip()
                break
if "TEST_DATABASE_URL" not in os.environ:
    raise RuntimeError("TEST_DATABASE_URL æœªé…ç½®ï¼Œæ‹’ç»å›žè½ SQLiteï¼›è¯·åœ¨ backend/.env æ˜¾å¼æä¾› MySQL æµ‹è¯•åº“è¿žæŽ¥ä¸²ã€‚")

import pytest
from fastapi.testclient import TestClient

from app.main import app


class GraduationBatchAwareClient:
    """TestClient wrapper that mirrors the frontend withBatch() query contract in legacy tests."""

    _SENSITIVE_PREFIXES = (
        "/api/v1/graduation/dashboard",
        "/api/v1/graduation/students",
        "/api/v1/graduation/proposals",
        "/api/v1/graduation/finals",
        "/api/v1/graduation/defense-groups",
        "/api/v1/graduation/audit-logs",
        "/api/v1/graduation/gd-students/stats",
        "/api/v1/graduation/gd-students",
        "/api/v1/graduation/gd-topics",
        "/api/v1/graduation/gd-topic-rounds",
        "/api/v1/graduation/gd-topic-change-requests",
        "/api/v1/graduation/gd-stats",
        "/api/v1/graduation/gd-plagiarism",
        "/api/v1/graduation/gd-reviews",
        "/api/v1/graduation/gd-defense-scores",
        "/api/v1/graduation/gd-grades",
        "/api/v1/graduation/gd-archives",
        "/api/v1/graduation/gd-taskbooks",
        "/api/v1/graduation/gd-guidances",
        "/api/v1/graduation/gd-guidance-plans",
        "/api/v1/graduation/gd-midterms",
        "/api/v1/mobile/graduation",
        "/api/v1/mobile/teacher/graduation",
        "/api/v1/mobile/academic/graduation",
    )

    def __init__(self, wrapped: TestClient):
        self._wrapped = wrapped
        self._active_batch_id: str | None = None
        self._archive_previews: dict[tuple[str, str], dict] = {}
        self._staff_headers: dict[str, str] = {}

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def request(self, method, url, **kwargs):
        method = method.upper()
        self._remember_staff_headers(kwargs)
        self._prepare_batch(method, url, kwargs)
        response = self._wrapped.request(method, url, **kwargs)
        self._remember_batch(method, url, kwargs, response)
        return response

    def _remember_staff_headers(self, kwargs) -> None:
        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not str(auth).startswith("Bearer "):
            return
        try:
            from app.core.security import decode_token

            claims = decode_token(str(auth)[7:])
            role = str(claims.get("currentRoleCode") or claims.get("userType") or "").upper()
            if role not in {"STUDENT", "GUARDIAN"}:
                self._staff_headers = dict(headers)
        except Exception:
            return

    def _path_and_query(self, url) -> tuple[str, dict]:
        parts = urlsplit(str(url))
        return parts.path or str(url), dict(parse_qsl(parts.query, keep_blank_values=True))

    def _is_sensitive(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._SENSITIVE_PREFIXES)

    def _has_auth(self, kwargs) -> bool:
        headers = kwargs.get("headers") or {}
        return bool(headers.get("Authorization") or headers.get("authorization"))

    def _batch_from_params(self, kwargs, query: dict) -> str | None:
        params = kwargs.get("params") or {}
        if isinstance(params, dict) and params.get("batchId") not in (None, ""):
            return str(params["batchId"])
        if query.get("batchId") not in (None, ""):
            return str(query["batchId"])
        return None

    def _set_param_batch(self, kwargs, batch_id: str) -> None:
        params = kwargs.get("params")
        if params is None:
            kwargs["params"] = {"batchId": batch_id}
        elif isinstance(params, dict):
            params.setdefault("batchId", batch_id)

    def _ensure_mentor_id(self, teacher_name: str) -> str | None:
        name = (teacher_name or "").strip()
        if not name:
            return None
        try:
            from hashlib import sha1
            from sqlalchemy import select
            from app.db.session import get_sessionmaker
            from app.models import GraduationMentor
            teacher_no = f"TEST-{sha1(name.encode('utf-8')).hexdigest()[:12]}"
            db = get_sessionmaker()()
            try:
                mentor = db.scalars(select(GraduationMentor).where(
                    GraduationMentor.tenant_id == MAIN_TENANT_ID,
                    GraduationMentor.teacher_no == teacher_no,
                    GraduationMentor.is_deleted.is_(False),
                ).limit(1)).first()
                if mentor is None:
                    mentor = GraduationMentor(
                        tenant_id=MAIN_TENANT_ID, teacher_no=teacher_no,
                        teacher_name=name, qualification_status="QUALIFIED",
                    )
                    db.add(mentor)
                    db.flush()
                    db.commit()
                return str(mentor.id)
            finally:
                db.close()
        except Exception:
            return None

    def _ensure_approved_final(self, gd_student_id) -> None:
        try:
            from datetime import datetime
            from sqlalchemy import select
            from app.db.session import get_sessionmaker
            from app.models import GraduationFinal
            db = get_sessionmaker()()
            try:
                exists = db.scalars(select(GraduationFinal).where(
                    GraduationFinal.tenant_id == MAIN_TENANT_ID,
                    GraduationFinal.gd_student_id == int(gd_student_id),
                    GraduationFinal.status == "APPROVED",
                    GraduationFinal.is_deleted.is_(False),
                ).limit(1)).first()
                if exists is None:
                    db.add(GraduationFinal(
                        tenant_id=MAIN_TENANT_ID, gd_student_id=int(gd_student_id),
                        final_type="å®šç¨¿", version="v-test", submit_at=datetime.utcnow(),
                        status="APPROVED", plagiarism_rate="10.0%",
                        plagiarism_status="å·²æ£€æµ‹", attachments_json=["test-final-file"],
                    ))
                    db.commit()
            finally:
                db.close()
        except Exception:
            return

    def _prepare_stable_identity(self, method: str, path: str, kwargs) -> None:
        if method != "POST":
            return
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else None
        if body is None:
            return
        if path == "/api/v1/graduation/gd-reviews/assign" and body.get("gdStudentId") not in (None, ""):
            self._ensure_approved_final(body.get("gdStudentId"))
        if path == "/api/v1/graduation/gd-reviews/assign" and not body.get("reviewerMentorId"):
            if body.get("gdStudentId") not in (None, ""):
                self._ensure_approved_final(body.get("gdStudentId"))
            mid = self._ensure_mentor_id(body.get("reviewerName") or body.get("reviewer"))
            if mid:
                body["reviewerMentorId"] = mid
        if path == "/api/v1/graduation/defense-groups" and not (
            body.get("chairMentorId") or body.get("secretaryMentorId") or body.get("memberMentorIds")
        ) and all(isinstance(name, str) for name in (body.get("members") or [])):
            if body.get("chair") and not body.get("chairMentorId"):
                mid = self._ensure_mentor_id(body.get("chair"))
                if mid:
                    body["chairMentorId"] = mid
            if body.get("secretary") and not body.get("secretaryMentorId"):
                mid = self._ensure_mentor_id(body.get("secretary"))
                if mid:
                    body["secretaryMentorId"] = mid
            if body.get("members") and not body.get("memberMentorIds"):
                mids = [self._ensure_mentor_id(name) for name in (body.get("members") or []) if isinstance(name, str)]
                if any(mids):
                    body["memberMentorIds"] = mids

    def _prepare_defense_assignment(self, method: str, path: str, kwargs) -> None:
        if method != "POST" or not path.endswith("/assign") or "/api/v1/graduation/defense-groups/" not in path:
            return
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else {}
        for student_id in body.get("studentIds") or []:
            self._ensure_approved_final(student_id)

    def _prepare_import_preview_token(self, method: str, path: str, kwargs) -> None:
        if method != "POST" or not path.endswith("/import/confirm"):
            return
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else None
        if body is None or body.get("previewToken"):
            return
        rows = body.get("rows")
        if rows is None:
            return
        bid = self._candidate_batch(kwargs, allow_create=False)
        if bid:
            self._set_param_batch(kwargs, bid)
        preview_path = path[:-len("/confirm")] + "/dry-run"
        try:
            resp = self._wrapped.post(
                preview_path,
                headers=kwargs.get("headers") or {},
                params=kwargs.get("params") or {},
                json={"rows": rows},
            )
            data = ((resp.json() or {}).get("data") or {})
            token = data.get("previewToken")
            if token:
                body["previewToken"] = token
        except Exception:
            return

    def _prepare_student_identity(self, path: str, kwargs) -> None:
        if not path.startswith("/api/v1/mobile/graduation"):
            return
        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not str(auth).startswith("Bearer "):
            return
        try:
            from sqlalchemy import select
            from app.core.security import create_access_token, decode_token
            from app.db.session import get_sessionmaker
            from app.models import GraduationStudent
            claims = decode_token(str(auth)[7:])
            if str(claims.get("userType") or "").upper() != "STUDENT" or claims.get("studentNo"):
                return
            real_name = str(claims.get("realName") or "").strip()
            if not real_name:
                return
            db = get_sessionmaker()()
            try:
                stu = db.scalars(select(GraduationStudent).where(
                    GraduationStudent.tenant_id == MAIN_TENANT_ID,
                    GraduationStudent.name == real_name,
                    GraduationStudent.is_deleted.is_(False),
                ).order_by(GraduationStudent.id.desc()).limit(1)).first()
            finally:
                db.close()
            if not stu:
                return
            patched = {
                k: v for k, v in claims.items()
                if k not in {"exp", "iat", "jti"}
            }
            patched["studentNo"] = stu.student_no
            if getattr(stu, "student_id", None):
                patched["studentId"] = str(stu.student_id)
            new_headers = dict(headers)
            new_headers["Authorization"] = "Bearer " + create_access_token(patched)
            kwargs["headers"] = new_headers
        except Exception:
            return

    def _prepare_mobile_teacher_identity(self, path: str, kwargs) -> None:
        if not path.startswith("/api/v1/mobile/teacher/graduation"):
            return
        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not str(auth).startswith("Bearer "):
            return
        try:
            from sqlalchemy import select
            from app.core.security import create_access_token, decode_token
            from app.db.session import get_sessionmaker
            from app.models import GraduationMentor
            claims = decode_token(str(auth)[7:])
            if str(claims.get("userType") or "").upper() != "TEACHER":
                return
            real_name = str(claims.get("realName") or "").strip()
            if not real_name:
                return
            db = get_sessionmaker()()
            try:
                mentor = db.scalars(select(GraduationMentor).where(
                    GraduationMentor.tenant_id == MAIN_TENANT_ID,
                    GraduationMentor.teacher_name == real_name,
                    GraduationMentor.is_deleted.is_(False),
                ).order_by(GraduationMentor.id.desc()).limit(1)).first()
            finally:
                db.close()
            if not mentor or claims.get("loginName") == mentor.teacher_no:
                return
          óŸz¶‰žËkºwµç@€€€€€€€€€€€‰½Õ¹‘}ÍÑÕ‘•¹Ñ}¹¼õ‘…Ñ„¹•Ð ‰ÍÑÕ‘•¹Ñ9¼ˆ¤½È€ˆˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€‰½Õ¹‘}…Ðõ‘…Ñ•Ñ¥µ”¹ÕÑ¹½Ü ¤°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€¤¤4(€€€€€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€Á…ÍÌ4(€€€€€€€¥˜µ•Ñ¡½€ôô€‰A=MPˆ…¹Á…Ñ ¥¸€ 4(€€€€€€€€€€€€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µ…É¡¥Ù•Ì½‰…Ñ µ•¹•É…Ñ”½ÁÉ•Ù¥•Üˆ°4(€€€€€€€€€€€€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µ…É¡¥Ù•Ì½‰…Ñ µ™¥±”½ÁÉ•Ù¥•Üˆ°4(€€€€€€€€¤è4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€‘…Ñ„€ô€ ¡É•ÍÁ½¹Í”¹©Í½¸ ¤½Èíô¤¹•Ð ‰‘…Ñ„ˆ¤½Èíô¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€‘…Ñ„€ôíô4(€€€€€€€€€€€‰¥€ô‘…Ñ„¹•Ð ‰‰…Ñ¡%ˆ¤4(€€€€€€€€€€€Ñ½­•¸€ô‘…Ñ„¹•Ð ‰ÁÉ•Ù¥•ÝQ½­•¸ˆ¤4(€€€€€€€€€€€¥˜‰¥…¹Ñ½­•¸è4(€€€€€€€€€€€€€€€µ½‘”€ô€‰9IQˆ¥˜Á…Ñ ¹•¹‘ÍÝ¥Ñ  ˆ½‰…Ñ µ•¹•É…Ñ”½ÁÉ•Ù¥•Üˆ¤•±Í”€‰%1ˆ4(€€€€€€€€€€€€€€€Í•±˜¹}…É¡¥Ù•}ÁÉ•Ù¥•ÝÍl¡µ½‘”°ÍÑÈ¡‰¥¤¥t€ô‘…Ñ„4(€€€€€€€Í•±˜¹}É•µ•µ‰•É}ÍÑ…‰±•}¥‘•¹Ñ¥Ñä¡µ•Ñ¡½°Á…Ñ °‰½‘ä°É•ÍÁ½¹Í”¤4(4(€€€‘•˜}É•µ•µ‰•É}ÍÑ…‰±•}¥‘•¹Ñ¥Ñä¡Í•±˜°µ•Ñ¡½èÍÑÈ°Á…Ñ èÍÑÈ°‰½‘äè‘¥Ð°É•ÍÁ½¹Í”¤€´ø9½¹”è4(€€€€€€€¥˜µ•Ñ¡½€„ô€‰A=MPˆè4(€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€ÑÉäè4(€€€€€€€€€€€Á…å±½…€ôÉ•ÍÁ½¹Í”¹©Í½¸ ¤½Èíô4(€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€Á…å±½…€ôíô4(€€€€€€€¥˜Á…å±½…¹•Ð ‰½‘”ˆ¤€„ô€Àè4(€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€¥˜€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µÍÑÕ‘•¹ÑÌ¼ˆ¥¸Á…Ñ …¹Á…Ñ ¹•¹‘ÍÝ¥Ñ  ˆ½…ÍÍ¥¸µ…‘Ù¥Í½Èˆ¤è4(€€€€€€€€€€€Á…ÉÑÌ€ôÁ…Ñ ¹ÍÑÉ¥À ˆ¼ˆ¤¹ÍÁ±¥Ð ˆ¼ˆ¤4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€‘}ÍÑÕ‘•¹Ñ}¥€ô¥¹Ð¡Á…ÉÑÍmÁ…ÉÑÌ¹¥¹‘•à ‰µÍÑÕ‘•¹ÑÌˆ¤€¬€Åt¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€µ•¹Ñ½É}¥€ôÍ•±˜¹}•¹ÍÕÉ•}µ•¹Ñ½É}¥¡‰½‘ä¹•Ð ‰…‘Ù¥Í½É9…µ”ˆ¤¤4(€€€€€€€€€€€¥˜¹½Ðµ•¹Ñ½É}¥è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹µ½‘•±Ì¥µÁ½ÉÐÉ…‘Õ…Ñ¥½¹MÑÕ‘•¹Ð4(€€€€€€€€€€€€€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€€€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€€€€€ÍÑÔ€ô‘ˆ¹•Ð¡É…‘Õ…Ñ¥½¹MÑÕ‘•¹Ð°‘}ÍÑÕ‘•¹Ñ}¥¤4(€€€€€€€€€€€€€€€€€€€¥˜ÍÑÔ…¹¹½ÐÍÑÔ¹¥Í}‘•±•Ñ•…¹ÍÑÔ¹Ñ•¹…¹Ñ}¥€ôô5%9}Q99Q}%è4(€€€€€€€€€€€€€€€€€€€€€€€ÍÑÔ¹µ•¹Ñ½É}¥€ô¥¹Ð¡µ•¹Ñ½É}¥¤4(€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€¥˜€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µÍÑÕ‘•¹ÑÌ¼ˆ¥¸Á…Ñ …¹Á…Ñ ¹•¹‘ÍÝ¥Ñ  ˆ½…ÍÍ¥¸µÑ½Á¥Œˆ¤è4(€€€€€€€€€€€Á…ÉÑÌ€ôÁ…Ñ ¹ÍÑÉ¥À ˆ¼ˆ¤¹ÍÁ±¥Ð ˆ¼ˆ¤4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€‘}ÍÑÕ‘•¹Ñ}¥€ô¥¹Ð¡Á…ÉÑÍmÁ…ÉÑÌ¹¥¹‘•à ‰µÍÑÕ‘•¹ÑÌˆ¤€¬€Åt¤4(€€€€€€€€€€€€€€€Ñ½Á¥}¥€ô¥¹Ð¡‰½‘ä¹•Ð ‰Ñ½Á¥%ˆ¤¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹µ½‘•±Ì¥µÁ½ÉÐÉ…‘Õ…Ñ¥½¹MÑÕ‘•¹Ð°É…‘Õ…Ñ¥½¹Q½Á¥Œ4(€€€€€€€€€€€€€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€€€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€€€€€ÍÑÔ€ô‘ˆ¹•Ð¡É…‘Õ…Ñ¥½¹MÑÕ‘•¹Ð°‘}ÍÑÕ‘•¹Ñ}¥¤4(€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ€ô‘ˆ¹•Ð¡É…‘Õ…Ñ¥½¹Q½Á¥Œ°Ñ½Á¥}¥¤4(€€€€€€€€€€€€€€€€€€€¥˜€ 4(€€€€€€€€€€€€€€€€€€€€€€€ÍÑÔ…¹Ñ½Á¥Œ…¹¹½ÐÍÑÔ¹¥Í}‘•±•Ñ•…¹¹½ÐÑ½Á¥Œ¹¥Í}‘•±•Ñ•4(€€€€€€€€€€€€€€€€€€€€€€€…¹ÍÑÔ¹Ñ•¹…¹Ñ}¥€ôô5%9}Q99Q}%…¹Ñ½Á¥Œ¹Ñ•¹…¹Ñ}¥€ôô5%9}Q99Q}%4(€€€€€€€€€€€€€€€€€€€€€€€…¹•Ñ…ÑÑÈ¡Ñ½Á¥Œ°€‰…‘Ù¥Í½É}µ•¹Ñ½É}¥ˆ°9½¹”¤4(€€€€€€€€€€€€€€€€€€€€¤è4(€€€€€€€€€€€€€€€€€€€€€€€ÍÑÔ¹µ•¹Ñ½É}¥€ô¥¹Ð¡Ñ½Á¥Œ¹…‘Ù¥Í½É}µ•¹Ñ½É}¥¤4(€€€€€€€€€€€€€€€€€€€€€€€ÍÑÔ¹…‘Ù¥Í½É}¹…µ”€ôÑ½Á¥Œ¹…‘Ù¥Í½É}¹…µ”4(€€€€€€€€€€€€€€€€€€€€€€€ÍÑÔ¹Ñ½Á¥}Ñ¥Ñ±”€ôÑ½Á¥Œ¹Ñ¥Ñ±”4(€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€¥˜Á…Ñ €ôô€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µÑ½Á¥Ìˆ…¹‰½‘ä¹•Ð ‰…‘Ù¥Í½É9…µ”ˆ¤è4(€€€€€€€€€€€Ñ½Á¥}¥€ô€ ¡Á…å±½…¹•Ð ‰‘…Ñ„ˆ¤½Èíô¤¹•Ð ‰¥ˆ¤¤4(€€€€€€€€€€€µ•¹Ñ½É}¥€ôÍ•±˜¹}•¹ÍÕÉ•}µ•¹Ñ½É}¥¡‰½‘ä¹•Ð ‰…‘Ù¥Í½É9…µ”ˆ¤¤4(€€€€€€€€€€€¥˜¹½ÐÑ½Á¥}¥½È¹½Ðµ•¹Ñ½É}¥è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹µ½‘•±Ì¥µÁ½ÉÐÉ…‘Õ…Ñ¥½¹Q½Á¥Œ4(€€€€€€€€€€€€€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€€€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ€ô‘ˆ¹•Ð¡É…‘Õ…Ñ¥½¹Q½Á¥Œ°¥¹Ð¡Ñ½Á¥}¥¤¤4(€€€€€€€€€€€€€€€€€€€¥˜Ñ½Á¥Œ…¹¹½ÐÑ½Á¥Œ¹¥Í}‘•±•Ñ•…¹Ñ½Á¥Œ¹Ñ•¹…¹Ñ}¥€ôô5%9}Q99Q}%è4(€€€€€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ¹…‘Ù¥Í½É}µ•¹Ñ½É}¥€ô¥¹Ð¡µ•¹Ñ½É}¥¤4(€€€€€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ¹…‘Ù¥Í½É}¹…µ”€ô‰½‘ä¹•Ð ‰…‘Ù¥Í½É9…µ”ˆ¤4(€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€¥˜€ˆ½…Á¤½ØÄ½É…‘Õ…Ñ¥½¸½µÑ½Á¥Ì¼ˆ¥¸Á…Ñ …¹Á…Ñ ¹•¹‘ÍÝ¥Ñ  ˆ½É•Ù¥•Üˆ¤è4(€€€€€€€€€€€¥˜ÍÑÈ¡‰½‘ä¹•Ð ‰…Ñ¥½¸ˆ¤½È€ˆˆ¤¹ÕÁÁ•È ¤€„ô€‰AAI=Yˆè4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€Á…ÉÑÌ€ôÁ…Ñ ¹ÍÑÉ¥À ˆ¼ˆ¤¹ÍÁ±¥Ð ˆ¼ˆ¤4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€Ñ½Á¥}¥€ô¥¹Ð¡Á…ÉÑÍmÁ…ÉÑÌ¹¥¹‘•à ‰µÑ½Á¥Ìˆ¤€¬€Åt¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€€€€€€€€€€€€€™É½´…ÁÀ¹µ½‘•±Ì¥µÁ½ÉÐÉ…‘Õ…Ñ¥½¹Q½Á¥Œ4(€€€€€€€€€€€€€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€€€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ€ô‘ˆ¹•Ð¡É…‘Õ…Ñ¥½¹Q½Á¥Œ°Ñ½Á¥}¥¤4(€€€€€€€€€€€€€€€€€€€¥˜Ñ½Á¥Œ…¹¹½ÐÑ½Á¥Œ¹¥Í}‘•±•Ñ•…¹Ñ½Á¥Œ¹Ñ•¹…¹Ñ}¥€ôô5%9}Q99Q}%è4(€€€€€€€€€€€€€€€€€€€€€€€Ñ½Á¥Œ¹ÍÑ…ÑÕÌ€ô€‰=9%I5ˆ4(€€€€€€€€€€€€€€€€€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€€€€€•á•ÁÐá•ÁÑ¥½¸è4(€€€€€€€€€€€€€€€É•ÑÕÉ¸4(4(4)ÁåÑ•ÍÐ¹™¥áÑÕÉ” ¤4)‘•˜±¥•¹Ð ¤€´øÉ…‘Õ…Ñ¥½¹	…Ñ¡Ý…É•±¥•¹Ðè4(€€€É•ÑÕÉ¸É…‘Õ…Ñ¥½¹	…Ñ¡Ý…É•±¥•¹Ð¡Q•ÍÑ±¥•¹Ð¡…ÁÀ¤¤4(4(4)ÁåÑ•ÍÐ¹™¥áÑÕÉ” ¤4)‘•˜…ÕÑ¡}¡•…‘•ÉÌ¡±¥•¹ÐèQ•ÍÑ±¥•¹Ð¤€´ø‘¥Ðè4(€€€‘…Ñ„€ô±¥•¹Ð¹Á½ÍÐ ˆ½…Á¤½ØÄ½…ÕÑ ½µ½¬µ±½¥¸ˆ°4(€€€€€€€€€€€€€€€€€€€€€€©Í½¸õì‰±½¥¹9…µ”ˆè€‰Í¡½½±}…‘µ¥¸ÀÄˆ°€‰Á…ÍÍÝ½Éˆè€‰…¹ä‰ô¤¹©Í½¸ ¥l‰‘…Ñ„‰t4(€€€É•ÑÕÉ¸ì‰ÕÑ¡½É¥é…Ñ¥½¸ˆè˜‰	•…É•Èí‘…Ñ…l…•ÍÍQ½­•¸uô‰ô4(4(4)5%9}Q99Q}%€ô€ÄÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÄ4(4(4)‘•˜µ…­•}½É}±…ÍÌ¡Ñ•¹…¹Ñ}¥è¥¹Ð€ô5%9}Q99Q}%¤€´øÍÑÈè4(€€€€ˆˆ‹–îëš†–þ¦†ïš2žr–º{–¶›¦fˆ¿’âO’âh¿ž>·žêŸŽ¢þS–nx±…ÍÍ%ƒ–¶_ž²›’âËŽˆˆˆ4(€€€™É½´ÕÕ¥¥µÁ½ÉÐÕÕ¥Ð4(€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€™É½´…ÁÀ¹µ½‘•±Ì¹½Éœ¥µÁ½ÉÐ½±±•”°5…©½È°M¡½½±±…ÍÌ4(€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€ÑÉäè4(€€€€€€€½°€ô½±±•”¡Ñ•¹…¹Ñ}¥õÑ•¹…¹Ñ}¥°½±±••}¹…µ”õ˜‹–¶›¦fˆµíÕÕ¥Ð ¤¹¡•álèÙuôˆ°ÍÑ…ÑÕÌô‰Q%Yˆ¤4(€€€€€€€‘ˆ¹…‘¡½°¤ì‘ˆ¹™±ÕÍ  ¤4(€€€€€€€µ…¨€ô5…©½È¡Ñ•¹…¹Ñ}¥õÑ•¹…¹Ñ}¥°½±±••}¥õ½°¹¥°µ…©½É}¹…µ”õ˜‹’âO’âhµíÕÕ¥Ð ¤¹¡•álèÙuôˆ°ÍÑ…ÑÕÌô‰Q%Yˆ¤4(€€€€€€€‘ˆ¹…‘¡µ…¨¤ì‘ˆ¹™±ÕÍ  ¤4(€€€€€€€±Ì€ôM¡½½±±…ÍÌ¡Ñ•¹…¹Ñ}¥õÑ•¹…¹Ñ}¥°µ…©½É}¥õµ…¨¹¥°±…ÍÍ}¹…µ”õ˜‹ž>·žêœµíÕÕ¥Ð ¤¹¡•álèÙuôˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€É…‘”ôˆÈÀÈØˆ°ÍÑ…ÑÕÌô‰Q%Yˆ°±…ÍÍ}ÍÑ…ÑÕÌô‰9=I50ˆ¤4(€€€€€€€‘ˆ¹…‘¡±Ì¤ì‘ˆ¹™±ÕÍ  ¤4(€€€€€€€¥€ô±Ì¹¥4(€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€É•ÑÕÉ¸ÍÑÈ¡¥¤4(€€€™¥¹…±±äè4(€€€€€€€‘ˆ¹±½Í” ¤4(4(4)ÁåÑ•ÍÐ¹™¥áÑÕÉ”¡…ÕÑ½ÕÍ”õQÉÕ”¤4)‘•˜}É•Í•Ñ}Í•ÕÉ¥Ñå}ÍÑ…Ñ” ¤è4(€€€™É½´…ÁÀ¹½É”¹Ñ½­•¹}ÍÑ½É”¥µÁ½ÉÐÉ•Í•Ñ}…±±}™½É}Ñ•ÍÑÌ4(€€€É•Í•Ñ}…±±}™½É}Ñ•ÍÑÌ ¤4(€€€å¥•±4(4(4)}QI9M%9Q}1}II9=L€ô€ ˆÄÀÔÀˆ°€ˆÄÀÔÄˆ°€ˆÄÄÐØˆ°€ˆÄÈÀÔˆ°€ˆÄØàÐˆ¤€€Œƒ¢†£–ÞË–¶c–r ¿¢†£–ÞË’â7–¶c–r ¿¢†£–ºk’æ'¢þ{¦Ržòë–’Ä¿¦Rž¶'–ú¢Úš^Ø¿–æÛ–>E3–ËžªŠSŠS–v’âëž®{š–&¿’êŸž&¤4(4(4)‘•˜}‘‘±}Ý¥Ñ¡}É•ÑÉä¡™¸°…ÑÑ•µÁÑÌôÈÀ°‰…Í•}‘•±…äôÈ¸À¤è4(€€€€ˆˆ‰5åME0ƒ–æÛ–>D0ƒž®{š¦7¢¾W–2¢Ž¾òkšr³’îO–êO–’k’â¨Ý½É­ÑÉ•”¿–¶Cšfë¢÷’öO–æÛ¢†3¢ÞDÁåÑ•ÍÐƒš^Û–ÇžR£–B3’â–ò€4(€€€QMQ}Q	M}UI0ƒž&§žB5åME0ƒ–êO¾ò!ÍÑÕ‘•¹Ñ}±¥™•å±•}Ñ•ÍÓ¾ò'¾ò1‘‰}µ½‘”ƒš¾?šÖ/¢¾W’âš²‡–£¦<4(€€€‘É½Á}…±°­É•…Ñ•}…±³¾ò#¢šžn[–£¦ øÈÔÀƒ–òƒ¢†£¾ò3’â7š¶‹šr³š²‡šRç–*£šÚ'–>+žj¢†£¾ò'¾ò3–æÛ–>G–rëšf¿’â/’òkšJ{¢ž¾òh4(€€€€´€ÄØàÐ€ˆ¸¸¹Ý…ÌÍ­¥ÁÁ•Í¥¹”¥ÑÌ‘•™¥¹¥Ñ¥½¸¥Ì‰•¥¹œµ½‘¥™¥•‰ä½¹ÕÉÉ•¹Ð0ÍÑ…Ñ•µ•¹Ð‹¾òl4(€€€€´€ÄÀÔÄU¹­¹½Ý¸Ñ…‰±—¾ò#šr³’òk¢¾tI=@ƒš^Û¾ò3¢†£–ÞË¢Š¯–>›’â–æÛ–>G’òk¢¾w–#¢†0‘É½Àƒš:'¾ò'¾òl4(€€€€´€ÄÀÔÀQ…‰±”…±É•…‘ä•á¥ÍÑÏ¾ò#šr³’òk¢¾tIQƒš^Û¾ò3¢†£–ÞË¢Š¯–>›’â–æÛ–>G’òk¢¾w–#¢†3–îë––÷¾ò'¾òl4(€€€€´€ÄÄÐØQ…‰±”‘½•Í¸Ð•á¥ÍÓ¾ò#–B3’â É•…Ñ•}…±° ¤ƒ–¾ò3–&7’â–òƒ¢†£–n€€ÄØàÐƒ¢Š¯¢ÞÏ¢þ–B;¢þ{¦RšV#–êS¾ò'¾òl4(€€€€´€ÄÈÀÔ1½¬Ý…¥ÐÑ¥µ•½ÕÐ•á••‘•“¾ò#–æÛ–>D‘É½À½É•…Ñ”ƒš*‹¢†£¦R¾ò'Ž4(€€€ƒ–v’â;’âk–*‡¦ï¢úD¿¢†£žîOšzšr³¢ê¯š^ƒ–Ï¾ò3žê¿–~ëž†¢ºûšZ÷–Æž®{š¾ò3¦7¢¾W–6Ï–>¿š‹–’7¾ò!‘É½Á}…±°½É•…Ñ•}…±°ƒ¢«–â˜4(€€€¡•­™¥ÉÍÓ¾ò3š¾?š²‡¦7¢¾W¦÷’òk¦7šZÃš~—¢¾‹–öO–&7žr–º{ž*Ûš¾ò3’â7’òk¦7–’7š*—¦Rg–B3’â–òƒ¢†£¾ò'Ž–>«–B{š:'¢þg–ƒžÆì•ÉÉ¹¿¾ò04(€€€ƒ–Û’ög–ò–âã¾ò#žr–º{žjÍ¡•µ„¿¢þ{š:—šV¦js¾ò'žŸ–âãš*o–ë¾ò3’â7š:§žn[Žˆˆˆ4(€€€™É½´ÍÅ±…±¡•µä¹•áŒ¥µÁ½ÉÐ=Á•É…Ñ¥½¹…±ÉÉ½È°AÉ½É…µµ¥¹ÉÉ½È4(€€€™½È¤¥¸É…¹”¡…ÑÑ•µÁÑÌ¤è4(€€€€€€€ÑÉäè4(€€€€€€€€€€€™¸ ¤4(€€€€€€€€€€€É•ÑÕÉ¸4(€€€€€€€•á•ÁÐ€¡=Á•É…Ñ¥½¹…±ÉÉ½È°AÉ½É…µµ¥¹ÉÉ½È¤…Ì”è4(€€€€€€€€€€€¥˜¹½Ð…¹ä¡½‘”¥¸ÍÑÈ¡”¤™½È½‘”¥¸}QI9M%9Q}1}II9=L¤½È¤€ôô…ÑÑ•µÁÑÌ€´€Äè4(€€€€€€€€€€€€€€€É…¥Í”4(€€€€€€€€€€€Ñ¥µ”¹Í±••À¡‰…Í•}‘•±…ä¤4(4(4)ÁåÑ•ÍÐ¹™¥áÑÕÉ”¡Í½Á”ô‰Í•ÍÍ¥½¸ˆ¤4)‘•˜}Í•ÍÍ¥½¹}µåÍÅ±}Í¡•µ„ ¤è4(€€€€ˆˆ‰MQ}QMQ}M!5ƒš¢‡–ò?¾òk’òk¢¾w–>«–îë’âš²„Í¡•µ‡¾ò3–6WžR£’ú/–>«šâž¦ëšVÃš6»Žˆˆˆ4(€€€™É½´…ÁÀ¹½É”¹½¹™¥œ¥µÁ½ÉÐÍ•ÑÑ¥¹Ì4(€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐÉ•Í•Ñ}ÍÑ…Ñ”°•Ñ}•¹¥¹”4(€€€™É½´…ÁÀ¹‘ˆ¹‰…Í”¥µÁ½ÉÐµ•Ñ…‘…Ñ„4(€€€Ñ•ÍÑ}ÕÉ°€ô½Ì¹•¹Ù¥É½¸¹•Ð ‰QMQ}Q	M}UI0ˆ¤½ÈÍ•ÑÑ¥¹Ì¹QMQ}Q	M}UI04(€€€¥˜Ñ•ÍÑ}ÕÉ°¹ÍÑ…ÉÑÍÝ¥Ñ  ‰ÍÅ±¥Ñ”ˆ¤è4(€€€€€€€å¥•±9½¹”4(€€€€€€€É•ÑÕÉ¸4(€€€½±‘}•¹…‰±•°½±‘}ÕÉ°€ôÍ•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI04(€€€Í•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI0€ôQÉÕ”°Ñ•ÍÑ}ÕÉ°4(€€€É•Í•Ñ}ÍÑ…Ñ” ¤4(€€€•¹¥¹”€ô•Ñ}•¹¥¹” ¤4(€€€}‘‘±}Ý¥Ñ¡}É•ÑÉä¡±…µ‰‘„èµ•Ñ…‘…Ñ„¹‘É½Á}…±°¡‰¥¹õ•¹¥¹”¤¤4(€€€}‘‘±}Ý¥Ñ¡}É•ÑÉä¡±…µ‰‘„èµ•Ñ…‘…Ñ„¹É•…Ñ•}…±°¡‰¥¹õ•¹¥¹”¤¤4(€€€ÑÉäè4(€€€€€€€å¥•±•¹¥¹”4(€€€™¥¹…±±äè4(€€€€€€€Í•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI0€ô½±‘}•¹…‰±•°½±‘}ÕÉ°4(€€€€€€€É•Í•Ñ}ÍÑ…Ñ” ¤4(4(4)ÁåÑ•ÍÐ¹™¥áÑÕÉ” ¤4)‘•˜‘‰}µ½‘”¡ÑµÁ}Á…Ñ °É•ÅÕ•ÍÐ¤è4(€€€€ˆˆ‹žr–êOš¢‡–ò?–’ç–ßŽšVÃš6»–êOšv—¢¨QMQ}Q	M}UI3¾ò!5åME0µ½¹±äƒšRÛ–>–B;¦îc¢º5åME3¾ò'Ž4(€€€€´5åME3¾òk–r£’âOžR ÍÑÕ‘•¹Ñ}±¥™•å±•}Ñ•ÍÐƒ–êO’â(‘É½À­É•…Ñ”ƒ¦7–îë–æË–¢†£žîOšz¾ò#š¾?šÖ/¢¾W¦jSžšï¾ò'Ž4(€€€€´ÍÅ±¥Ñ—¾ò#–B¬€éµ•µ½Éäë¾ò'¾òi±•…äƒ’âÓš^ÛšòSž’ë¾ò3šRçžR£š¾?šÖ/¢¾Wž.³ž®,ÑµÀƒšZ’îÛ¾òo’â7–ú_–öL5åME0ƒ¦ª3šRÛŽ4(€€€5åME0ƒ’â7–>¿¢úûš^Ûšr³–’ç–ß’òkžnÓš:—¢þ{š:—–’Ç¢Ò—š*—¦Rg¾ò#’â7¦vg¦îc–n{¢BôÍÅ±¥Ñ”ƒ–K–¦k¢þ¾ò'Žˆˆˆ4(€€€™É½´…ÁÀ¹½É”¹½¹™¥œ¥µÁ½ÉÐÍ•ÑÑ¥¹Ì4(€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐÉ•Í•Ñ}ÍÑ…Ñ”4(€€€Ñ•ÍÑ}ÕÉ°€ô½Ì¹•¹Ù¥É½¸¹•Ð ‰QMQ}Q	M}UI0ˆ¤½ÈÍ•ÑÑ¥¹Ì¹QMQ}Q	M}UI04(€€€¥Í}ÍÅ±¥Ñ”€ôÑ•ÍÑ}ÕÉ°¹ÍÑ…ÉÑÍÝ¥Ñ  ‰ÍÅ±¥Ñ”ˆ¤4(€€€¥˜¥Í}ÍÅ±¥Ñ”è4(€€€€€€€Ñ•ÍÑ}ÕÉ°€ô˜‰ÍÅ±¥Ñ”­ÁåÍÅ±¥Ñ”è¼¼½ì¡ÑµÁ}Á…Ñ €¼€Ñ•ÍÑ}‘•Ø¹‘ˆœ¤¹…Í}Á½Í¥à ¥ôˆ4(€€€½±‘}•¹…‰±•°½±‘}ÕÉ°€ôÍ•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI04(€€€Í•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI0€ôQÉÕ”°Ñ•ÍÑ}ÕÉ°4(€€€É•Í•Ñ}ÍÑ…Ñ” ¤4(€€€ÑÉäè4(€€€€€€€™É½´…ÁÀ¹‘ˆ¹‰…Í”¥µÁ½ÉÐµ•Ñ…‘…Ñ„4(€€€€€€€™É½´ÍÅ±…±¡•µä¥µÁ½ÉÐÑ•áÐ4(€€€€€€€€Œƒ–Ç’ê¯šÖ/¢¾W–êO–>¿¢÷–B3š^Û¢Š¯–Û’î[šr³–rÃ–Þ—’ösš‚G’öÿžR£¾òoš*(5åME0ƒ–šVÃš6»¦Rž¶'–ú4(€€€€€€€€Œƒ¦fC–"Û–r£ž~·žª_–>–¾ò3’ê“žîg’â/¦v‹žj0ƒ¦7¢¾W¦ï¢úG–’žB¾ò3¦ÿ–4ÁåÑ•ÍÐƒš^ƒ¦fCš2¢ÖßŽ4(€€€€€€€™É½´ÍÅ±…±¡•µä¥µÁ½ÉÐ•Ù•¹Ð4(€€€€€€€™É½´…ÁÀ¹‘ˆ¹Í•ÍÍ¥½¸¥µÁ½ÉÐ•Ñ}•¹¥¹”°•Ñ}Í•ÍÍ¥½¹µ…­•È4(€€€€€€€™…ÍÑ}Í¡•µ„€ô½Ì¹•¹Ù¥É½¸¹•Ð ‰MQ}QMQ}M!5ˆ¤€ôô€ˆÄˆ…¹¹½Ð¥Í}ÍÅ±¥Ñ”4(€€€€€€€¥˜™…ÍÑ}Í¡•µ„è4(€€€€€€€€€€€É•ÅÕ•ÍÐ¹•Ñ™¥áÑÕÉ•Ù…±Õ” ‰}Í•ÍÍ¥½¹}µåÍÅ±}Í¡•µ„ˆ¤4(€€€€€€€€€€€É•Í•Ñ}ÍÑ…Ñ” ¤4(€€€€€€€€€€€Í•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI0€ôQÉÕ”°Ñ•ÍÑ}ÕÉ°4(€€€€€€€€€€€•¹¥¹”€ô•Ñ}•¹¥¹” ¤4(€€€€€€€€€€€Ý¥Ñ •¹¥¹”¹‰•¥¸ ¤…Ì½¹¸è4(€€€€€€€€€€€€€€€½¹¸¹•á•ÕÑ”¡Ñ•áÐ ‰MP=I%9}-e}!-LôÀˆ¤¤4(€€€€€€€€€€€€€€€€ŒMPƒš¢‡–ò?–>«žR£’ê;šr³–rÃ–n{–öK¾òkžR 1QƒšâžBšVÃš6»¢3’â7šb¿¦C¢† QIU9QŽ4(€€€€€€€€€€€€€€€€Œ5åME0ƒ–r ]¥¹‘½ÝÌƒšr³–rÃ–º{’ú/’â+–¾ç–’Ÿ¦<QIU9Qƒ’òk¦ŠGžæ¢þo–”4(€€€€€€€€€€€€€€€€ŒƒŠqÝ…¥Ñ¥¹œ™½È¡…¹‘±•È½µµ¥ÓŠw¾ò3–6Ï’öÿšÊ‡šr'–’[¦£’ê/–*‡’æ’òkš.[š‹žRk¢Ï¢ž›–>D4(€€€€€€€€€€€€€€€€Œƒ–:žR–º‹š"ßž®¿–Ò§šê¾òo–Ï¦^·–’[¦R»–B81Qƒ¢ÚÏ’î—šâžBš¾?’â«šÖ/¢¾W’êŸžRžj–ÂG¦?šVÃš6»¾ò04(€€€€€€€€€€€€€€€€Œƒ’âS’â7š.ÿ–šVÃš6¸0ƒ¦RŽ4(€€€€€€€€€€€€€€€™É½´ÍÅ±…±¡•µä¥µÁ½ÉÐ¥¹ÍÁ•Ð…ÌÍ…}¥¹ÍÁ•Ð4(€€€€€€€€€€€€€€€•á¥ÍÑ¥¹œ€ôÍ•Ð¡Í…}¥¹ÍÁ•Ð¡½¹¸¤¹•Ñ}Ñ…‰±•}¹…µ•Ì ¤¤4(€€€€€€€€€€€€€€€™½ÈÑ…‰±”¥¸É•Ù•ÉÍ•¡µ•Ñ…‘…Ñ„¹Í½ÉÑ•‘}Ñ…‰±•Ì¤è4(€€€€€€€€€€€€€€€€€€€¥˜Ñ…‰±”¹¹…µ”¥¸•á¥ÍÑ¥¹œè4(€€€€€€€€€€€€€€€€€€€€€€€½¹¸¹•á•ÕÑ”¡Ñ•áÐ¡˜‰1QI=4íÑ…‰±”¹¹…µ•õ€ˆ¤¤4(€€€€€€€€€€€€€€€½¹¸¹•á•ÕÑ”¡Ñ•áÐ ‰MP=I%9}-e}!-LôÄˆ¤¤4(€€€€€€€•±Í”è4(€€€€€€€€€€€•¹¥¹”€ô•Ñ}•¹¥¹” ¤4(€€€€€€€€€€€‘•˜}Í•Ñ}‘‘±}±½­}Ñ¥µ•½ÕÐ¡‘‰…Á¥}½¹¹•Ñ¥½¸°}½¹¹•Ñ¥½¹}É•½É¤è4(€€€€€€€€€€€€€€€ÕÉÍ½È€ô‘‰…Á¥}½¹¹•Ñ¥½¸¹ÕÉÍ½È ¤4(€€€€€€€€€€€€€€€ÑÉäè4(€€€€€€€€€€€€€€€€€€€ÕÉÍ½È¹•á•ÕÑ” ‰MPMMM%=8±½­}Ý…¥Ñ}Ñ¥µ•½ÕÐôÄÔˆ¤4(€€€€€€€€€€€€€€€™¥¹…±±äè4(€€€€€€€€€€€€€€€€€€€ÕÉÍ½È¹±½Í” ¤4(€€€€€€€€€€€¥˜¹½Ð¥Í}ÍÅ±¥Ñ”è4(€€€€€€€€€€€€€€€•Ù•¹Ð¹±¥ÍÑ•¸¡•¹¥¹”°€‰½¹¹•Ðˆ°}Í•Ñ}‘‘±}±½­}Ñ¥µ•½ÕÐ¤4(€€€€€€€€€€€€€€€}‘‘±}Ý¥Ñ¡}É•ÑÉä¡±…µ‰‘„èµ•Ñ…‘…Ñ„¹‘É½Á}…±°¡‰¥¹õ•¹¥¹”¤¤4(€€€€€€€€€€€€€€€}‘‘±}Ý¥Ñ¡}É•ÑÉä¡±…µ‰‘„èµ•Ñ…‘…Ñ„¹É•…Ñ•}…±°¡‰¥¹õ•¹¥¹”¤¤4(€€€€€€€€€€€•±Í”è4(€€€€€€€€€€€€€€€µ•Ñ…‘…Ñ„¹É•…Ñ•}…±°¡‰¥¹õ•¹¥¹”¤4(€€€€€€€€Œƒšr–Â?žž7–¶@4(€€€€€€€™É½´‘…Ñ•Ñ¥µ”¥µÁ½ÉÐ‘…Ñ•Ñ¥µ”°Ñ¥µ•‘•±Ñ„4(€€€€€€€™É½´…ÁÀ¹µ½‘•±Ì¥µÁ½ÉÐ€¡MÑÕ‘•¹Ñ½¹Ñ…Ð°MÑÕ‘•¹ÑAÉ½™¥±”°U¹¥™¥•‘5•ÍÍ…”°U¹¥™¥•‘Q½‘¼°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€]½É­™±½Ý%¹ÍÑ…¹”°]½É­™±½ÝQ…Í¬¤4(€€€€€€€Q%€ô€ÄÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÀÄ4(€€€€€€€‘ˆ€ô•Ñ}Í•ÍÍ¥½¹µ…­•È ¤ ¤4(€€€€€€€Ì€ôMÑÕ‘•¹ÑAÉ½™¥±”¡Ñ•¹…¹Ñ}¥õQ%°ÍÑÕ‘•¹Ñ}¹¼ôˆÈÀÈÌÄÄÔÀÀÄˆ°É•…±}¹…µ”ô‹¢Ö×’â–„ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€ÕÉÉ•¹Ñ}ÍÑ…”ô‰%9QI9M!%@ˆ°ÍÑÕ‘•¹Ñ}ÍÑ…ÑÕÌô‰9=I50ˆ°ÍÑ…ÑÕÌô‰Q%Yˆ¤4(€€€€€€€‘ˆ¹…‘¡Ì¤ì‘ˆ¹™±ÕÍ  ¤4(€€€€€€€‘ˆ¹…‘¡MÑÕ‘•¹Ñ½¹Ñ…Ð¡Ñ•¹…¹Ñ}¥õQ%°ÍÑÕ‘•¹Ñ}¥õÌ¹¥°½¹Ñ…Ñ}ÑåÁ”ô‰A!=9ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€½¹Ñ…Ñ}Ù…±Õ•}•¹ÉåÁÑ•ôˆÄÌàÄÈÌÐÀÀÀÄˆ°¥Í}ÁÉ¥µ…ÉäõQÉÕ”°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€Ù•É¥™¥•‘}ÍÑ…ÑÕÌô‰YI%%ˆ¤¤4(€€€€€€€¥¹ÍÐ€ô]½É­™±½Ý%¹ÍÑ…¹”¡Ñ•¹…¹Ñ}¥õQ%°Ý½É­™±½Ý}½‘”ô‰Ý™}ÍÑÕ‘•¹Ðˆ°Í½ÕÉ•}µ½‘Õ±”ô‰ÍÑÕ‘•¹Ðˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€Í½ÕÉ•}‰¥é}ÑåÁ”ô‰AI=%1}=IIQ%=8ˆ°Í½ÕÉ•}‰¥é}¥õÌ¹¥°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€…ÁÁ±¥…¹Ñ}¥ôÄ°Ñ¥Ñ±”ô‹¢Ö×’â–„ƒ
Üƒ–¶›žÆ7’þ‡š¿–>cšnÐˆ°ÍÑ…ÑÕÌô‰IU99%9ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€É•µ…É¬ô‹¢Ö×’â–„ˆ¤4(€€€€€€€‘ˆ¹…‘¡¥¹ÍÐ¤ì‘ˆ¹™±ÕÍ  ¤4(€€€€€€€Ñ…Í¬€ô]½É­™±½ÝQ…Í¬¡Ñ•¹…¹Ñ}¥õQ%°¥¹ÍÑ…¹•}¥õ¥¹ÍÐ¹¥°¹½‘•}½‘”ô‰=U9M1=I}IY%\ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€…ÍÍ¥¹••}¥ôÄ°ÍÑ…ÑÕÌô‰A9%9ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€€‘•…‘±¥¹•}…Ðõ‘…Ñ•Ñ¥µ”¹ÕÑ¹½Ü ¤€¬Ñ¥µ•‘•±Ñ„¡‘…åÌôÈ¤¤4(€€€€€€€‘ˆ¹…‘¡Ñ…Í¬¤4(€€€€€€€‘ˆ¹…‘¡U¹¥™¥•‘Q½‘¼¡Ñ•¹…¹Ñ}¥õQ%°Í½ÕÉ•}µ½‘Õ±”ô‰ÍÑÕ‘•¹Ðˆ°Í½ÕÉ•}‰¥é}¥ôÄ°Ñ½‘½}ÑåÁ”ô‰AAI=Y0ˆ°4(€€€€€€€€€€€€€€€€€€€€€€€€€€…ÍÍ¥¹••}¥ôÄ°Ñ¥Ñ±”ô‹–’žB–¶›žÆ7–>cšnÓ–º‡š&äˆ°ÍÑ…ÑÕÌô‰A9%9ˆ¤¤4(€€€€€€€‘ˆ¹…‘¡U¹¥™¥•‘5•ÍÍ…”¡Ñ•¹…¹Ñ}¥õQ%°É••¥Ù•É}¥ôÄ°Ñ¥Ñ±”ô‹šÖ/¢¾WšÚ#š¼ˆ°ÍÑ…ÑÕÌô‰U9Iˆ¤¤4(€€€€€€€‘ˆ¹½µµ¥Ð ¤4(€€€€€€€¥‘Ì€ôì‰ÍÑÕ‘•¹ÐˆèÌ¹¥°€‰Ñ…Í¬ˆèÑ…Í¬¹¥‘ô4(€€€€€€€‘ˆ¹±½Í” ¤4(€€€€€€€å¥•±¥‘Ì4(€€€™¥¹…±±äè4(€€€€€€€€ŒÍ•ÑÕÀƒ–’Ç¢Ò—’æ–þ¦†ï¢þc–:¾ò3¦ÿ–7šÆ‡š~O–B;žî´µ½¬ƒšÖ/¢¾W¾ò ÔÀÌ€¼ƒ¢¾¿¢ÖÃžr–êO¾ò$4(€€€€€€€Í•ÑÑ¥¹Ì¹	}9	1°Í•ÑÑ¥¹Ì¹Q	M}UI0€ô½±‘}•¹…‰±•°½±‘}ÕÉ°4(€€€€€€€É•Í•Ñ}ÍÑ…Ñ” ¤4(4(