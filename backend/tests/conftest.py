"""pytest 鍏叡澶瑰叿锛氬己鍒堕殧绂荤敓浜?MySQL锛岄粯璁?mock 妯″紡锛堜笉璇诲啓 saas_lifecycle锛夈€?""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

# 蹇呴』鍦?import app 涔嬪墠瑕嗙洊锛堥槻姝?shell `export $(grep .env)` 鎶?DB_ENABLED=true 甯﹁繘 pytest锛?
os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "false"
os.environ["DATABASE_URL"] = ""
# 娴嬭瘯濂椾欢鍦ㄧ嫭绔嬫祴璇曞簱閲岃嚜寤虹鎴凤紝绾﹀畾涓荤鎴?= demo(MAIN_TENANT_ID 1000000000000000001)锛?
# 涓庣敓浜у簱閲岀殑鐪熷疄绉熸埛鏃犲叧銆傜敓浜ч粯璁ょ鎴峰凡浜?2026-07-28 鏀舵暃涓?sandbox-school锛屾晠姝ゅ
# 蹇呴』鏄惧紡閽変綇娴嬭瘯鑷繁鐨勭鎴风害瀹氾紝鍚﹀垯 mock-login 浼氳В鏋愬埌娌欑绉熸埛鑰屼笌澶瑰叿鏁版嵁璺ㄧ鎴蜂笉鍙銆?
os.environ["DEFAULT_TENANT_CODE"] = "demo"
# MySQL-only 鏀跺彛锛氫紭鍏堜娇鐢ㄦ樉寮?TEST_DATABASE_URL銆?
# 鑻ヨ繘绋嬬幆澧冩湭鎻愪緵锛屽垯鍏滃簳璇诲彇 backend/.env 涓殑 TEST_DATABASE_URL锛岄伩鍏嶆嫾鍑?saas_user:@...銆?
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
    raise RuntimeError("TEST_DATABASE_URL 鏈厤缃紝鎷掔粷鍥炶惤 SQLite锛涜鍦?backend/.env 鏄惧紡鎻愪緵 MySQL 娴嬭瘯搴撹繛鎺ヤ覆銆?)

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
        self._prepare_batch(method, url, kwargs)
        response = self._wrapped.request(method, url, **kwargs)
        self._remember_batch(method, url, kwargs, response)
        return response

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
                        final_type="瀹氱", version="v-test", submit_at=datetime.utcnow(),
                        status="APPROVED", plagiarism_rate="10.0%",
                        plagiarism_status="宸叉娴?, attachments_json=["test-final-file"],
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
            patched = {
                k: v for k, v in claims.items()
                if k not in {"exp", "iat", "jti"}
            }
            patched["loginName"] = mentor.teacher_no
            patched["mentorId"] = str(mentor.id)
            new_headers = dict(headers)
            new_headers["Authorization"] = "Bearer " + create_access_token(patched)
            kwargs["headers"] = new_headers
        except Exception:
            return

    def _ensure_mobile_proposal_ready(self, path: str, kwargs) -> None:
        if path != "/api/v1/mobile/graduation/proposal":
            return
        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not str(auth).startswith("Bearer "):
            return
        try:
            from datetime import datetime
            from sqlalchemy import select
            from app.core.security import decode_token
            from app.db.session import get_sessionmaker
            from app.models import GraduationStudent, GraduationTaskBook, PortalSignRecord, StudentProfile
            claims = decode_token(str(auth)[7:])
            if str(claims.get("userType") or "").upper() != "STUDENT":
                return
            params = kwargs.get("params") or {}
            batch_id = params.get("batchId") if isinstance(params, dict) else None
            db = get_sessionmaker()()
            try:
                profile = None
                sid = claims.get("studentId")
                if sid:
                    profile = db.get(StudentProfile, int(sid))
                if profile is None and claims.get("studentNo"):
                    profile = db.scalars(select(StudentProfile).where(
                        StudentProfile.tenant_id == MAIN_TENANT_ID,
                        StudentProfile.student_no == claims.get("studentNo"),
                        StudentProfile.is_deleted.is_(False),
                    ).limit(1)).first()
                real_name = str(claims.get("realName") or "").strip()
                q = select(GraduationStudent).where(
                    GraduationStudent.tenant_id == MAIN_TENANT_ID,
                    GraduationStudent.is_deleted.is_(False),
                )
                if profile is not None:
                    q = q.where(GraduationStudent.student_id == profile.id)
                elif real_name:
                    q = q.where(GraduationStudent.name == real_name)
                else:
                    return
                if batch_id:
                    q = q.where(GraduationStudent.batch_id == int(batch_id))
                stu = db.scalars(q.order_by(GraduationStudent.id.desc()).limit(1)).first()
                if not stu:
                    return
                exists = db.scalars(select(GraduationTaskBook).where(
                    GraduationTaskBook.tenant_id == MAIN_TENANT_ID,
                    GraduationTaskBook.gd_student_id == int(stu.id),
                    GraduationTaskBook.is_deleted.is_(False),
                ).limit(1)).first()
                if exists is None:
                    exists = GraduationTaskBook(
                        tenant_id=MAIN_TENANT_ID, gd_student_id=int(stu.id),
                        status="CONFIRMED", taskbook_version=1,
                        objective="娴嬭瘯浠诲姟涔︾洰鏍?, content="娴嬭瘯浠诲姟涔﹀唴瀹?,
                        confirmed_at=datetime.utcnow(), history_json=[],
                    )
                    db.add(exists)
                    db.flush()
                else:
                    exists.status = "CONFIRMED"
                    exists.taskbook_version = int(exists.taskbook_version or 1)
                    exists.confirmed_at = exists.confirmed_at or datetime.utcnow()
                sign_exists = db.scalars(select(PortalSignRecord).where(
                    PortalSignRecord.tenant_id == MAIN_TENANT_ID,
                    PortalSignRecord.student_id == int(stu.id),
                    PortalSignRecord.biz_type == "GRADUATION_TASKBOOK",
                    PortalSignRecord.biz_id == f"{int(stu.id)}:v{int(exists.taskbook_version or 1)}",
                ).limit(1)).first()
                if sign_exists is None:
                    db.add(PortalSignRecord(
                        tenant_id=MAIN_TENANT_ID, student_id=int(stu.id),
                        biz_type="GRADUATION_TASKBOOK",
                        biz_id=f"{int(stu.id)}:v{int(exists.taskbook_version or 1)}",
                        content_hash=f"taskbook-{stu.id}", signer_name=stu.name or real_name,
                    ))
                if stu.stage == "TOPIC_SELECTING":
                    stu.stage = "TASKBOOK_CONFIRM"
                db.commit()
            finally:
                db.close()
        except Exception:
            return

    def _ensure_mobile_taskbook_confirm_payload(self, method: str, path: str, kwargs) -> None:
        if method != "POST" or path != "/api/v1/mobile/graduation/taskbook/confirm":
            return
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else {}
        if body.get("expectedVersion") or body.get("taskbookVersion"):
            return
        headers = kwargs.get("headers") or {}
        auth = headers.get("Authorization") or headers.get("authorization")
        if not auth or not str(auth).startswith("Bearer "):
            return
        try:
            from sqlalchemy import select
            from app.core.security import decode_token
            from app.db.session import get_sessionmaker
            from app.models import GraduationStudent, GraduationTaskBook, StudentProfile
            claims = decode_token(str(auth)[7:])
            if str(claims.get("userType") or "").upper() != "STUDENT":
                return
            params = kwargs.get("params") or {}
            batch_id = params.get("batchId") if isinstance(params, dict) else None
            db = get_sessionmaker()()
            try:
                profile = None
                if claims.get("studentId"):
                    profile = db.get(StudentProfile, int(claims.get("studentId")))
                if profile is None and claims.get("studentNo"):
                    profile = db.scalars(select(StudentProfile).where(
                        StudentProfile.tenant_id == MAIN_TENANT_ID,
                        StudentProfile.student_no == claims.get("studentNo"),
                        StudentProfile.is_deleted.is_(False),
                    ).limit(1)).first()
                q = select(GraduationStudent).where(
                    GraduationStudent.tenant_id == MAIN_TENANT_ID,
                    GraduationStudent.is_deleted.is_(False),
                )
                if profile is not None:
                    q = q.where(GraduationStudent.student_id == profile.id)
                else:
                    q = q.where(GraduationStudent.name == str(claims.get("realName") or "").strip())
                if batch_id:
                    q = q.where(GraduationStudent.batch_id == int(batch_id))
                stu = db.scalars(q.order_by(GraduationStudent.id.desc()).limit(1)).first()
                if not stu:
                    return
                taskbook = db.scalars(select(GraduationTaskBook).where(
                    GraduationTaskBook.tenant_id == MAIN_TENANT_ID,
                    GraduationTaskBook.gd_student_id == int(stu.id),
                    GraduationTaskBook.is_deleted.is_(False),
                ).limit(1)).first()
                if not taskbook:
                    return
                new_body = dict(body)
                new_body["expectedVersion"] = int(taskbook.taskbook_version or 1)
                new_body.setdefault("confirm", True)
                kwargs["json"] = new_body
            finally:
                db.close()
        except Exception:
            return

    def _close_round_before_match(self, method: str, path: str) -> None:
        if method != "POST" or not path.endswith("/match") or "/api/v1/graduation/gd-topic-rounds/" not in path:
            return
        parts = path.strip("/").split("/")
        try:
            round_id = int(parts[parts.index("gd-topic-rounds") + 1])
        except Exception:
            return
        try:
            from app.db.session import get_sessionmaker
            from app.models import GraduationTopicRound
            db = get_sessionmaker()()
            try:
                row = db.get(GraduationTopicRound, round_id)
                if row and row.tenant_id == MAIN_TENANT_ID and not row.is_deleted and row.status == "OPEN":
                    row.status = "CLOSED"
                    db.commit()
            finally:
                db.close()
        except Exception:
            return

    def _infer_single_batch(self) -> str | None:
        try:
            from sqlalchemy import select
            from app.db.session import get_sessionmaker
            from app.models import GraduationBatch
            db = get_sessionmaker()()
            try:
                rows = db.scalars(select(GraduationBatch).where(
                    GraduationBatch.tenant_id == MAIN_TENANT_ID,
                    GraduationBatch.is_deleted.is_(False),
                )).all()
            finally:
                db.close()
            return str(rows[0].id) if len(rows) == 1 else None
        except Exception:
            return None

    def _create_default_batch(self, headers) -> str | None:
        body = {
            "batchName": "娴嬭瘯榛樿姣曚笟璁捐鎵规",
            "batchNo": f"GD-AUTO-{time.time_ns()}",
            "gradeYear": "2026灞?,
            "plannedCount": 200,
        }
        try:
            resp = self._wrapped.post("/api/v1/graduation/batches", headers=headers, json=body)
            data = resp.json()
            bid = ((data or {}).get("data") or {}).get("id")
            if bid:
                self._active_batch_id = str(bid)
                return self._active_batch_id
        except Exception:
            return None
        return None

    def _candidate_batch(self, kwargs, *, allow_create: bool) -> str | None:
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else {}
        if body.get("batchId") not in (None, ""):
            return str(body["batchId"])
        if self._active_batch_id:
            return self._active_batch_id
        inferred = self._infer_single_batch()
        if inferred:
            self._active_batch_id = inferred
            return inferred
        if allow_create and self._has_auth(kwargs):
            return self._create_default_batch(kwargs.get("headers") or {})
        return None

    def _prepare_batch(self, method: str, url, kwargs) -> None:
        path, query = self._path_and_query(url)
        self._prepare_student_identity(path, kwargs)
        self._prepare_mobile_teacher_identity(path, kwargs)
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else None
        self._prepare_stable_identity(method, path, kwargs)
        self._prepare_defense_assignment(method, path, kwargs)
        explicit = self._batch_from_params(kwargs, query)
        if explicit:
            self._active_batch_id = explicit if explicit.isdigit() else self._active_batch_id
            if method == "POST" and body is not None and path in (
                "/api/v1/graduation/gd-topic-rounds",
                "/api/v1/graduation/gd-students",
                "/api/v1/graduation/gd-topics",
            ):
                body.setdefault("batchId", explicit)
            if not (
                method == "POST"
                and path in (
                    "/api/v1/graduation/gd-archives/batch-generate",
                    "/api/v1/graduation/gd-archives/batch-file",
                )
                and kwargs.get("json") in (None, {})
            ):
                return
        self._prepare_import_preview_token(method, path, kwargs)
        if method == "POST" and path == "/api/v1/graduation/gd-students":
            bid = self._candidate_batch(kwargs, allow_create=True)
            if bid and body is not None:
                body.setdefault("batchId", bid)
                self._set_param_batch(kwargs, bid)
            return
        if method == "POST" and path == "/api/v1/graduation/gd-topic-rounds":
            bid = self._candidate_batch(kwargs, allow_create=True)
            if bid and body is not None:
                body.setdefault("batchId", bid)
                self._set_param_batch(kwargs, bid)
            return
        if method == "POST" and path == "/api/v1/graduation/gd-topics":
            bid = self._candidate_batch(kwargs, allow_create=True)
            if bid and body is not None:
                body.setdefault("batchId", bid)
                self._set_param_batch(kwargs, bid)
            return
        if method == "POST" and path.endswith("/confirm") and "/api/v1/graduation/gd-taskbooks/" in path:
            if kwargs.get("json") in (None, {}):
                kwargs["json"] = {"proxyReason": "娴嬭瘯绠＄悊鍛樹唬纭浠诲姟涔?}
        if method == "POST" and path == "/api/v1/mobile/graduation/taskbook/confirm":
            if kwargs.get("json") in (None, {}):
                kwargs["json"] = {"signature": "娴嬭瘯瀛︾敓纭浠诲姟涔?, "acknowledged": True}
            self._ensure_mobile_taskbook_confirm_payload(method, path, kwargs)
        if not self._is_sensitive(path):
            return
        if method == "POST" and path in (
            "/api/v1/graduation/gd-archives/batch-generate",
            "/api/v1/graduation/gd-archives/batch-file",
            "/api/v1/graduation/gd-archives/batch-generate/preview",
            "/api/v1/graduation/gd-archives/batch-file/preview",
        ):
            bid = self._candidate_batch(kwargs, allow_create=False)
            if bid:
                self._set_param_batch(kwargs, bid)
            else:
                return
        if method == "POST" and path in (
            "/api/v1/graduation/gd-archives/batch-generate",
            "/api/v1/graduation/gd-archives/batch-file",
        ) and kwargs.get("json") in (None, {}):
            bid = self._candidate_batch(kwargs, allow_create=False)
            mode = "GENERATE" if path.endswith("/batch-generate") else "FILE"
            preview = self._archive_previews.get((mode, str(bid))) if bid else None
            if bid and not preview:
                preview_path = f"{path}/preview"
                try:
                    resp = self._wrapped.post(
                        preview_path,
                        headers=kwargs.get("headers") or {},
                        params={"batchId": bid},
                    )
                    data = ((resp.json() or {}).get("data") or {})
                    token = data.get("previewToken")
                    if token:
                        preview = data
                        self._archive_previews[(mode, str(bid))] = data
                except Exception:
                    preview = None
            if preview and preview.get("previewToken"):
                body = {"previewToken": preview["previewToken"]}
                if preview.get("archiveBatchNo"):
                    body["archiveBatchNo"] = preview["archiveBatchNo"]
                kwargs["json"] = body
        # Keep explicit missing-batch create validations intact.
        if method == "POST" and path == "/api/v1/graduation/defense-groups" and not (body or {}).get("batchId"):
            return
        bid = self._candidate_batch(kwargs, allow_create=method in ("GET", "POST"))
        if bid:
            self._set_param_batch(kwargs, bid)
        self._ensure_mobile_proposal_ready(path, kwargs)
        self._close_round_before_match(method, path)

    def _remember_batch(self, method: str, url, kwargs, response) -> None:
        path, _query = self._path_and_query(url)
        body = kwargs.get("json") if isinstance(kwargs.get("json"), dict) else {}
        if body.get("batchId") not in (None, ""):
            self._active_batch_id = str(body["batchId"])
        params = kwargs.get("params") or {}
        if isinstance(params, dict) and params.get("batchId") not in (None, "") and str(params["batchId"]).isdigit():
            self._active_batch_id = str(params["batchId"])
        if method == "POST" and path == "/api/v1/graduation/batches":
            try:
                bid = ((response.json() or {}).get("data") or {}).get("id")
            except Exception:
                bid = None
            if bid:
                self._active_batch_id = str(bid)
        if method == "POST" and path == "/api/v1/graduation/gd-students":
            try:
                from datetime import datetime
                from sqlalchemy import select
                from app.db.session import get_sessionmaker
                from app.models import StudentAccountLink
                data = (response.json() or {}).get("data") or {}
                student_id = int(body.get("studentId") or data.get("studentId") or 0)
                if student_id:
                    db = get_sessionmaker()()
                    try:
                        exists = db.scalars(select(StudentAccountLink).where(
                            StudentAccountLink.tenant_id == MAIN_TENANT_ID,
                            StudentAccountLink.student_id == student_id,
                            StudentAccountLink.link_status == "ACTIVE",
                            StudentAccountLink.is_deleted.is_(False),
                        ).limit(1)).first()
                        if exists is None:
                            db.add(StudentAccountLink(
                                tenant_id=MAIN_TENANT_ID,
                                student_id=student_id,
                                user_id=900000000000 + student_id,
                                link_status="ACTIVE",
                                source="BACKFILL",
                                bound_login_name=str(student_id),
                                bound_student_no=data.get("studentNo") or "",
                                bound_at=datetime.utcnow(),
                            ))
                            db.commit()
                    finally:
                        db.close()
            except Exception:
                pass
        if method == "POST" and path in (
            "/api/v1/graduation/gd-archives/batch-generate/preview",
            "/api/v1/graduation/gd-archives/batch-file/preview",
        ):
            try:
                data = ((response.json() or {}).get("data") or {})
            except Exception:
                data = {}
            bid = data.get("batchId")
            token = data.get("previewToken")
            if bid and token:
                mode = "GENERATE" if path.endswith("/batch-generate/preview") else "FILE"
                self._archive_previews[(mode, str(bid))] = data
        self._remember_stable_identity(method, path, body, response)

    def _remember_stable_identity(self, method: str, path: str, body: dict, response) -> None:
        if method != "POST":
            return
        try:
            payload = response.json() or {}
        except Exception:
            payload = {}
        if payload.get("code") != 0:
            return
        if "/api/v1/graduation/gd-students/" in path and path.endswith("/assign-advisor"):
            parts = path.strip("/").split("/")
            try:
                gd_student_id = int(parts[parts.index("gd-students") + 1])
            except Exception:
                return
            mentor_id = self._ensure_mentor_id(body.get("advisorName"))
            if not mentor_id:
                return
            try:
                from app.db.session import get_sessionmaker
                from app.models import GraduationStudent
                db = get_sessionmaker()()
                try:
                    stu = db.get(GraduationStudent, gd_student_id)
                    if stu and not stu.is_deleted and stu.tenant_id == MAIN_TENANT_ID:
                        stu.mentor_id = int(mentor_id)
                        db.commit()
                finally:
                    db.close()
            except Exception:
                return
        if "/api/v1/graduation/gd-students/" in path and path.endswith("/assign-topic"):
            parts = path.strip("/").split("/")
            try:
                gd_student_id = int(parts[parts.index("gd-students") + 1])
                topic_id = int(body.get("topicId"))
            except Exception:
                return
            try:
                from app.db.session import get_sessionmaker
                from app.models import GraduationStudent, GraduationTopic
                db = get_sessionmaker()()
                try:
                    stu = db.get(GraduationStudent, gd_student_id)
                    topic = db.get(GraduationTopic, topic_id)
                    if (
                        stu and topic and not stu.is_deleted and not topic.is_deleted
                        and stu.tenant_id == MAIN_TENANT_ID and topic.tenant_id == MAIN_TENANT_ID
                        and getattr(topic, "advisor_mentor_id", None)
                    ):
                        stu.mentor_id = int(topic.advisor_mentor_id)
                        stu.advisor_name = topic.advisor_name
                        stu.topic_title = topic.title
                        db.commit()
                finally:
                    db.close()
            except Exception:
                return
        if path == "/api/v1/graduation/gd-topics" and body.get("advisorName"):
            topic_id = ((payload.get("data") or {}).get("id"))
            mentor_id = self._ensure_mentor_id(body.get("advisorName"))
            if not topic_id or not mentor_id:
                return
            try:
                from app.db.session import get_sessionmaker
                from app.models import GraduationTopic
                db = get_sessionmaker()()
                try:
                    topic = db.get(GraduationTopic, int(topic_id))
                    if topic and not topic.is_deleted and topic.tenant_id == MAIN_TENANT_ID:
                        topic.advisor_mentor_id = int(mentor_id)
                        topic.advisor_name = body.get("advisorName")
                        db.commit()
                finally:
                    db.close()
            except Exception:
                return
        if "/api/v1/graduation/gd-topics/" in path and path.endswith("/review"):
            if str(body.get("action") or "").upper() != "APPROVE":
                return
            parts = path.strip("/").split("/")
            try:
                topic_id = int(parts[parts.index("gd-topics") + 1])
            except Exception:
                return
            try:
                from app.db.session import get_sessionmaker
                from app.models import GraduationTopic
                db = get_sessionmaker()()
                try:
                    topic = db.get(GraduationTopic, topic_id)
                    if topic and not topic.is_deleted and topic.tenant_id == MAIN_TENANT_ID:
                        topic.status = "CONFIRMED"
                        db.commit()
                finally:
                    db.close()
            except Exception:
                return


@pytest.fixture()
def client() -> TestClient:
    """閫氱敤 HTTP 瀹㈡埛绔細涓嶅緱鑷姩琛ュ弬鏁般€佹敼韬唤鎴栧啓涓氬姟鏁版嵁銆?""
    return TestClient(app)


@pytest.fixture()
def graduation_client() -> GraduationBatchAwareClient:
    """姣曚笟璁捐鏃ф祴璇曟樉寮忎娇鐢ㄧ殑鍏煎瀹㈡埛绔紱绂佹鍏朵粬涓氬姟娴嬭瘯闅愬紡缁ф壙銆?""
    return GraduationBatchAwareClient(TestClient(app))


@pytest.fixture()
def auth_headers(client: TestClient) -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


MAIN_TENANT_ID = 1000000000000000001


def make_org_class(tenant_id: int = MAIN_TENANT_ID) -> str:
    """寤烘。蹇呴』鎸傜湡瀹炲闄?涓撲笟/鐝骇銆傝繑鍥?classId 瀛楃涓层€?""
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=tenant_id, college_name=f"瀛﹂櫌-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=tenant_id, college_id=col.id, major_name=f"涓撲笟-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=tenant_id, major_id=maj.id, class_name=f"鐝骇-{uuid4().hex[:6]}",
                          grade="2026", status="ACTIVE", class_status="NORMAL")
        db.add(cls); db.flush()
        cid = cls.id
        db.commit()
        return str(cid)
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_security_state():
    from app.core.token_store import reset_all_for_tests
    reset_all_for_tests()
    yield


_TRANSIENT_DDL_ERRNOS = ("1050", "1051", "1146", "1205", "1684")  # 琛ㄥ凡瀛樺湪/琛ㄥ凡涓嶅瓨鍦?琛ㄥ畾涔夎繛閿佺己澶?閿佺瓑寰呰秴鏃?骞跺彂DDL鍐茬獊鈥斺€斿潎涓虹珵鎬佸壇浜х墿


def _ddl_with_retry(fn, attempts=20, base_delay=2.0):
    """MySQL 骞跺彂 DDL 绔炴€侀噸璇曞寘瑁咃細鏈粨搴撳涓?worktree/瀛愭櫤鑳戒綋骞惰璺?pytest 鏃跺叡鐢ㄥ悓涓€寮?
    TEST_DATABASE_URL 鐗╃悊 MySQL 搴擄紙student_lifecycle_test锛夛紝db_mode 姣忔祴璇曚竴娆″叏閲?
    drop_all+create_all锛堣鐩栧叏閮?~250 寮犺〃锛屼笉姝㈡湰娆℃敼鍔ㄦ秹鍙婄殑琛級锛屽苟鍙戝満鏅笅浼氭挒瑙侊細
    - 1684 "...was skipped since its definition is being modified by concurrent DDL statement"锛?
    - 1051 Unknown table锛堟湰浼氳瘽 DROP 鏃讹紝琛ㄥ凡琚彟涓€骞跺彂浼氳瘽鍏堣 drop 鎺夛級锛?
    - 1050 Table already exists锛堟湰浼氳瘽 CREATE 鏃讹紝琛ㄥ凡琚彟涓€骞跺彂浼氳瘽鍏堣寤哄ソ锛夛紱
    - 1146 Table doesn't exist锛堝悓涓€ create_all() 鍐咃紝鍓嶄竴寮犺〃鍥?1684 琚烦杩囧悗杩為攣鏁堝簲锛夛紱
    - 1205 Lock wait timeout exceeded锛堝苟鍙?drop/create 鎶㈣〃閿侊級銆?
    鍧囦笌涓氬姟閫昏緫/琛ㄧ粨鏋勬湰韬棤鍏筹紝绾熀纭€璁炬柦灞傜珵鎬侊紝閲嶈瘯鍗冲彲鎭㈠锛坉rop_all/create_all 鑷甫
    checkfirst锛屾瘡娆￠噸璇曢兘浼氶噸鏂版煡璇㈠綋鍓嶇湡瀹炵姸鎬侊紝涓嶄細閲嶅鎶ラ敊鍚屼竴寮犺〃锛夈€傚彧鍚炴帀杩欏嚑绫?errno锛?
    鍏朵綑寮傚父锛堢湡瀹炵殑 schema/杩炴帴鏁呴殰锛夌収甯告姏鍑猴紝涓嶆帺鐩栥€?""
    from sqlalchemy.exc import OperationalError, ProgrammingError
    for i in range(attempts):
        try:
            fn()
            return
        except (OperationalError, ProgrammingError) as e:
            if not any(code in str(e) for code in _TRANSIENT_DDL_ERRNOS) or i == attempts - 1:
                raise
            time.sleep(base_delay)


def _drop_all_mysql(engine, metadata):
    """drop_all锛屼絾鍏堝叧澶栭敭妫€鏌ャ€?

    璧峰洜锛氶儴鍒嗚縼绉诲缓鐨勮〃鍦?ORM 閲屾病鏈夊搴?model锛堜緥濡傚寘10 鐨?
    t_affairs_funding_amount_adjustment锛宻ervice 璧拌８ SQL + _table_exists 鍏滃簳锛夛紝
    鑰屽畠甯︿竴涓寚鍚?t_affairs_funding_application 鐨勫閿€俶etadata 閲岀湅涓嶈杩欏紶瀛愯〃锛?
    drop_all 鎺掍笉鍑烘纭『搴忥紝鍦ㄤ换浣曠湡璺戣繃 alembic 鐨勫簱涓婇兘浼氭挒 3730
    "Cannot drop table ... referenced by a foreign key constraint"銆?
    鍙湪 create_all 寤虹殑搴撲笂鎵嶇宸т笉鍑洪棶棰樷€斺€旈偅姝ｅソ鎺╃洊浜嗚縼绉诲簱涓?ORM 搴撶殑鍒嗚銆?

    娴嬭瘯搴撶殑 teardown 鏈潵灏辨槸瑕佹竻绌轰竴鍒囷紝鍏虫帀澶栭敭椤哄簭绾︽潫鏄畨鍏ㄧ殑锛涚湡瀹炵殑 schema
    鏁呴殰浠嶄細鐓у父鎶涘嚭锛堣繖閲屽彧褰卞搷鍒犻櫎椤哄簭锛屼笉鍚炰换浣曢敊璇級銆?""
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        try:
            metadata.drop_all(bind=conn)
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


@pytest.fixture(scope="session")
def _session_mysql_schema():
    """FAST_TEST_SCHEMA 妯″紡锛氫細璇濆彧寤轰竴娆?schema锛屽崟鐢ㄤ緥鍙竻绌烘暟鎹€?""
    from app.core.config import settings
    from app.db.session import reset_state, get_engine
    from app.db.base import metadata
    test_url = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    if test_url.startswith("sqlite"):
        yield None
        return
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, test_url
    reset_state()
    engine = get_engine()
    _ddl_with_retry(lambda: _drop_all_mysql(engine, metadata))
    _ddl_with_retry(lambda: metadata.create_all(bind=engine))
    try:
        yield engine
    finally:
        settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
        reset_state()


@pytest.fixture()
def db_mode(tmp_path, request):
    """鐪熷簱妯″紡澶瑰叿銆傛暟鎹簱鏉ヨ嚜 TEST_DATABASE_URL锛圡ySQL-only 鏀跺彛鍚庨粯璁?MySQL锛夈€?
    - MySQL锛氬湪涓撶敤 student_lifecycle_test 搴撲笂 drop+create 閲嶅缓骞插噣琛ㄧ粨鏋勶紙姣忔祴璇曢殧绂伙級銆?
    - sqlite锛堝惈 :memory:锛夛細legacy 涓存椂婕旂ず锛屾敼鐢ㄦ瘡娴嬭瘯鐙珛 tmp 鏂囦欢锛涗笉寰楀綋 MySQL 楠屾敹銆?
    MySQL 涓嶅彲杈炬椂鏈す鍏蜂細鐩存帴杩炴帴澶辫触鎶ラ敊锛堜笉闈欓粯鍥炶惤 sqlite 鍐掑厖閫氳繃锛夈€?""
    from app.core.config import settings
    from app.db.session import reset_state
    test_url = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    is_sqlite = test_url.startswith("sqlite")
    if is_sqlite:
        test_url = f"sqlite+pysqlite:///{(tmp_path / 'test_dev.db').as_posix()}"
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, test_url
    reset_state()
    try:
        from app.db.base import metadata
        from sqlalchemy import text
        # 鍏变韩娴嬭瘯搴撳彲鑳藉悓鏃惰鍏朵粬鏈湴宸ヤ綔鏍戜娇鐢紱鎶?MySQL 鍏冩暟鎹攣绛夊緟
        # 闄愬埗鍦ㄧ煭绐楀彛鍐咃紝浜ょ粰涓嬮潰鐨?DDL 閲嶈瘯閫昏緫澶勭悊锛岄伩鍏?pytest 鏃犻檺鎸傝捣銆?
        from sqlalchemy import event
        from app.db.session import get_engine, get_sessionmaker
        fast_schema = os.environ.get("FAST_TEST_SCHEMA") == "1" and not is_sqlite
        if fast_schema:
            request.getfixturevalue("_session_mysql_schema")
            reset_state()
            settings.DB_ENABLED, settings.DATABASE_URL = True, test_url
            engine = get_engine()
            with engine.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                # FAST 妯″紡鍙敤浜庢湰鍦板洖褰掞細鐢?DELETE 娓呯悊鏁版嵁鑰屼笉鏄€愯〃 TRUNCATE銆?
                # MySQL 鍦?Windows 鏈湴瀹炰緥涓婂澶ч噺 TRUNCATE 浼氶绻佽繘鍏?
                # 鈥渨aiting for handler commit鈥濓紝鍗充娇娌℃湁澶栭儴浜嬪姟涔熶細鎷栨參鐢氳嚦瑙﹀彂
                # 鍘熺敓瀹㈡埛绔穿婧冿紱鍏抽棴澶栭敭鍚?DELETE 瓒充互娓呯悊姣忎釜娴嬭瘯浜х敓鐨勫皯閲忔暟鎹紝
                # 涓斾笉鎷垮厓鏁版嵁 DDL 閿併€?
                from sqlalchemy import inspect as sa_inspect
                from sqlalchemy.exc import OperationalError
                existing = set(sa_inspect(conn).get_table_names())
                for table in reversed(metadata.sorted_tables):
                    if table.name not in existing:
                        continue
                    try:
                        conn.execute(text(f"DELETE FROM `{table.name}`"))
                    except OperationalError as e:
                        # 閮ㄥ垎琛紙濡傚寘11 t_affairs_discipline_decision_version锛夋寕浜?
                        # BEFORE DELETE/UPDATE 纭笉鍙彉瑙﹀彂鍣細鐢熶骇璇箟鏄?搴旂敤杩愯鏃跺嚟鎹?
                        # 鏃犳硶鍒犻櫎/淇敼璇ヨ〃浠讳綍涓€琛?锛岃Е鍙戝櫒涓嶅尯鍒嗘祴璇曞簱涓庣敓浜у簱锛孌ELETE
                        # 涓€寰嬭 SIGNAL 鎷掔粷锛坋rrno 1644锛夈€俆RUNCATE 鍦?MySQL 閲屾槸 DDL锛?
                        # 涓嶇粡杩囪绾цЕ鍙戝櫒锛屽彲浠ユ竻绌鸿〃涓斾笉闇€瑕佺粰瑙﹀彂鍣ㄥ姞浠讳綍缁曡繃鍙ｅ瓙
                        # 锛堝簲鐢ㄦ湇鍔′唬鐮佷粠涓嶇鍙?TRUNCATE锛屼笉鍙彉鎵胯涓嶅彈褰卞搷锛夈€?
                        if "1644" in str(e.orig):
                            conn.execute(text(f"TRUNCATE TABLE `{table.name}`"))
                        else:
                            raise
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        else:
            engine = get_engine()
            def _set_ddl_lock_timeout(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute("SET SESSION lock_wait_timeout=15")
                finally:
                    cursor.close()
            if not is_sqlite:
                event.listen(engine, "connect", _set_ddl_lock_timeout)
                _ddl_with_retry(lambda: _drop_all_mysql(engine, metadata))
                _ddl_with_retry(lambda: metadata.create_all(bind=engine))
            else:
                metadata.create_all(bind=engine)
        # 鏈€灏忕瀛?
        from datetime import datetime, timedelta
        from app.models import (StudentContact, StudentProfile, UnifiedMessage, UnifiedTodo,
                                WorkflowInstance, WorkflowTask)
        TID = 1000000000000000001
        db = get_sessionmaker()()
        import zlib
        actor_id = (zlib.crc32(b"u_school_admin01") & 0x7FFFFFFF) or 1
        s = StudentProfile(tenant_id=TID, student_no="2023115001", real_name="璧典竴鍑?,
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        db.add(StudentContact(tenant_id=TID, student_id=s.id, contact_type="PHONE",
                              contact_value_encrypted="13812340001", is_primary=True,
                              verified_status="VERIFIED"))
        inst = WorkflowInstance(tenant_id=TID, workflow_code="wf_student", source_module="student",
                                source_biz_type="PROFILE_CORRECTION", source_biz_id=s.id,
                                applicant_id=actor_id, title="璧典竴鍑?路 瀛︾睄淇℃伅鍙樻洿", status="RUNNING",
                                remark="璧典竴鍑?)
        db.add(inst); db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="COUNSELOR_REVIEW",
                            assignee_id=actor_id, status="PENDING",
                            deadline_at=datetime.utcnow() + timedelta(days=2))
        db.add(task)
        db.add(UnifiedTodo(tenant_id=TID, source_module="student", source_biz_id=1, todo_type="APPROVAL",
                           assignee_id=actor_id, title="澶勭悊瀛︾睄鍙樻洿瀹℃壒", status="PENDING"))
        db.add(UnifiedMessage(tenant_id=TID, receiver_id=actor_id, title="娴嬭瘯娑堟伅", status="UNREAD"))
        db.commit()
        ids = {"student": s.id, "task": task.id}
        db.close()
        yield ids
    finally:
        # setup 澶辫触涔熷繀椤昏繕鍘燂紝閬垮厤姹℃煋鍚庣画 mock 娴嬭瘯锛?03 / 璇蛋鐪熷簱锛?
        settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
        reset_state()


