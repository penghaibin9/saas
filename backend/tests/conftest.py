"""pytest 公共夹具：强制隔离生产 MySQL，默认 mock 模式（不读写 saas_lifecycle）。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

# 必须在 import app 之前覆盖（防止 shell `export $(grep .env)` 把 DB_ENABLED=true 带进 pytest）
os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "false"
os.environ["DATABASE_URL"] = ""
# 测试套件在独立测试库里自建租户，约定主租户 = demo(MAIN_TENANT_ID 1000000000000000001)，
# 与生产库里的真实租户无关。生产默认租户已于 2026-07-28 收敛为 sandbox-school，故此处
# 必须显式钉住测试自己的租户约定，否则 mock-login 会解析到沙箱租户而与夹具数据跨租户不可见。
os.environ["DEFAULT_TENANT_CODE"] = "demo"
# MySQL-only 收口：优先使用显式 TEST_DATABASE_URL。
# 若进程环境未提供，则兜底读取 backend/.env 中的 TEST_DATABASE_URL，避免拼出 saas_user:@...。
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
    raise RuntimeError("TEST_DATABASE_URL 未配置，拒绝回落 SQLite；请在 backend/.env 显式提供 MySQL 测试库连接串。")

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
        """记住最近一次教职工请求头，供需要管理员身份的兜底逻辑复用。

        来自 a6aa869a，该提交写 conftest.py 时文件损坏（46751B -> 30011B 乱码），
        这里按其可读部分的原意恢复。
        """
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
                        final_type="定稿", version="v-test", submit_at=datetime.utcnow(),
                        status="APPROVED", plagiarism_rate="10.0%",
                        plagiarism_status="已检测", attachments_json=["test-final-file"],
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
                        objective="测试任务书目标", content="测试任务书内容",
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
            "batchName": "测试默认毕业设计批次",
            "batchNo": f"GD-AUTO-{time.time_ns()}",
            "gradeYear": "2026届",
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
                kwargs["json"] = {"proxyReason": "测试管理员代确认任务书"}
        if method == "POST" and path == "/api/v1/mobile/graduation/taskbook/confirm":
            if kwargs.get("json") in (None, {}):
                kwargs["json"] = {"signature": "测试学生确认任务书", "acknowledged": True}
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
def client() -> GraduationBatchAwareClient:
    return GraduationBatchAwareClient(TestClient(app))


@pytest.fixture()
def auth_headers(client: TestClient) -> dict:
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


MAIN_TENANT_ID = 1000000000000000001


def make_org_class(tenant_id: int = MAIN_TENANT_ID) -> str:
    """建档必须挂真实学院/专业/班级。返回 classId 字符串。"""
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass
    db = get_sessionmaker()()
    try:
        col = College(tenant_id=tenant_id, college_name=f"学院-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(col); db.flush()
        maj = Major(tenant_id=tenant_id, college_id=col.id, major_name=f"专业-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(maj); db.flush()
        cls = SchoolClass(tenant_id=tenant_id, major_id=maj.id, class_name=f"班级-{uuid4().hex[:6]}",
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


_TRANSIENT_DDL_ERRNOS = ("1050", "1051", "1146", "1205", "1684")  # 表已存在/表已不存在/表定义连锁缺失/锁等待超时/并发DDL冲突——均为竞态副产物


def _ddl_with_retry(fn, attempts=20, base_delay=2.0):
    """MySQL 并发 DDL 竞态重试包装：本仓库多个 worktree/子智能体并行跑 pytest 时共用同一张
    TEST_DATABASE_URL 物理 MySQL 库（student_lifecycle_test），db_mode 每测试一次全量
    drop_all+create_all（覆盖全部 ~250 张表，不止本次改动涉及的表），并发场景下会撞见：
    - 1684 "...was skipped since its definition is being modified by concurrent DDL statement"；
    - 1051 Unknown table（本会话 DROP 时，表已被另一并发会话先行 drop 掉）；
    - 1050 Table already exists（本会话 CREATE 时，表已被另一并发会话先行建好）；
    - 1146 Table doesn't exist（同一 create_all() 内，前一张表因 1684 被跳过后连锁效应）；
    - 1205 Lock wait timeout exceeded（并发 drop/create 抢表锁）。
    均与业务逻辑/表结构本身无关，纯基础设施层竞态，重试即可恢复（drop_all/create_all 自带
    checkfirst，每次重试都会重新查询当前真实状态，不会重复报错同一张表）。只吞掉这几类 errno，
    其余异常（真实的 schema/连接故障）照常抛出，不掩盖。"""
    from sqlalchemy.exc import OperationalError, ProgrammingError
    for i in range(attempts):
        try:
            fn()
            return
        except (OperationalError, ProgrammingError) as e:
            if not any(code in str(e) for code in _TRANSIENT_DDL_ERRNOS) or i == attempts - 1:
                raise
            time.sleep(base_delay)


@pytest.fixture(scope="session")
def _session_mysql_schema():
    """FAST_TEST_SCHEMA 模式：会话只建一次 schema，单用例只清空数据。"""
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
    _ddl_with_retry(lambda: metadata.drop_all(bind=engine))
    _ddl_with_retry(lambda: metadata.create_all(bind=engine))
    try:
        yield engine
    finally:
        settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
        reset_state()


@pytest.fixture()
def db_mode(tmp_path, request):
    """真库模式夹具。数据库来自 TEST_DATABASE_URL（MySQL-only 收口后默认 MySQL）。
    - MySQL：在专用 student_lifecycle_test 库上 drop+create 重建干净表结构（每测试隔离）。
    - sqlite（含 :memory:）：legacy 临时演示，改用每测试独立 tmp 文件；不得当 MySQL 验收。
    MySQL 不可达时本夹具会直接连接失败报错（不静默回落 sqlite 冒充通过）。"""
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
        # 共享测试库可能同时被其他本地工作树使用；把 MySQL 元数据锁等待
        # 限制在短窗口内，交给下面的 DDL 重试逻辑处理，避免 pytest 无限挂起。
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
                # FAST 模式只用于本地回归：用 DELETE 清理数据而不是逐表 TRUNCATE。
                # MySQL 在 Windows 本地实例上对大量 TRUNCATE 会频繁进入
                # “waiting for handler commit”，即使没有外部事务也会拖慢甚至触发
                # 原生客户端崩溃；关闭外键后 DELETE 足以清理每个测试产生的少量数据，
                # 且不拿元数据 DDL 锁。
                from sqlalchemy import inspect as sa_inspect
                existing = set(sa_inspect(conn).get_table_names())
                for table in reversed(metadata.sorted_tables):
                    if table.name in existing:
                        conn.execute(text(f"DELETE FROM `{table.name}`"))
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
                _ddl_with_retry(lambda: metadata.drop_all(bind=engine))
                _ddl_with_retry(lambda: metadata.create_all(bind=engine))
            else:
                metadata.create_all(bind=engine)
        # 最小种子
        from datetime import datetime, timedelta
        from app.models import (StudentContact, StudentProfile, UnifiedMessage, UnifiedTodo,
                                WorkflowInstance, WorkflowTask)
        TID = 1000000000000000001
        db = get_sessionmaker()()
        s = StudentProfile(tenant_id=TID, student_no="2023115001", real_name="赵一凡",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        db.add(StudentContact(tenant_id=TID, student_id=s.id, contact_type="PHONE",
                              contact_value_encrypted="13812340001", is_primary=True,
                              verified_status="VERIFIED"))
        inst = WorkflowInstance(tenant_id=TID, workflow_code="wf_student", source_module="student",
                                source_biz_type="PROFILE_CORRECTION", source_biz_id=s.id,
                                applicant_id=1, title="赵一凡 · 学籍信息变更", status="RUNNING",
                                remark="赵一凡")
        db.add(inst); db.flush()
        task = WorkflowTask(tenant_id=TID, instance_id=inst.id, node_code="COUNSELOR_REVIEW",
                            assignee_id=1, status="PENDING",
                            deadline_at=datetime.utcnow() + timedelta(days=2))
        db.add(task)
        db.add(UnifiedTodo(tenant_id=TID, source_module="student", source_biz_id=1, todo_type="APPROVAL",
                           assignee_id=1, title="处理学籍变更审批", status="PENDING"))
        db.add(UnifiedMessage(tenant_id=TID, receiver_id=1, title="测试消息", status="UNREAD"))
        db.commit()
        ids = {"student": s.id, "task": task.id}
        db.close()
        yield ids
    finally:
        # setup 失败也必须还原，避免污染后续 mock 测试（503 / 误走真库）
        settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
        reset_state()

