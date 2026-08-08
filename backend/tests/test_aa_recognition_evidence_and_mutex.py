"""成绩认定证据链与并发互斥回归（P0-D06 扩面 + P0-N02 认定侧）。

成绩认定终审和免修终审一样，直接生成一条计学分的正式及格成绩，佐证就是这门学分的唯一依据。
两个洞原来在两边同时敞着：

1. 证据治理：只校验"fileId 属于本租户"，拿别人的文件、审批期间换掉内容都发现不了；
2. 并发：submit 的查重是 SELECT-then-INSERT 无锁，两个申请双双落库，各自终审后给同一个学生
   同一门课生成两条 attempt_no 相同且都 PASSED 的正式成绩——
   (source_biz_type, source_biz_id) 唯一键拦不住，因为两条来源本来就不同。

MySQL-only（db_mode 夹具）。
"""
from __future__ import annotations

import threading
from datetime import datetime
from types import SimpleNamespace

import pytest

TID = 1000000000000000001


def _ctx(user_id=100, student_no="RG2401", student_id=None):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    actor = {
        "userId": str(user_id), "tenantId": str(TID), "realName": "认定甲",
        "currentRoleCode": "STUDENT", "activeContextId": "ctx", "userType": "STUDENT",
        "studentNo": student_no,
    }
    if student_id:
        actor["studentId"] = str(student_id)
    set_current_user(actor)
    return actor


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _student(db, student_no="RG2401", name="认定甲"):
    from app.models import StudentProfile

    row = StudentProfile(tenant_id=TID, student_no=student_no, real_name=name,
                         grade="2024", student_status="NORMAL", status="ACTIVE")
    db.add(row)
    db.flush()
    return row


def _course(db, code="RG_MATH", name="高等数学"):
    from app.models import AaCourse

    row = AaCourse(tenant_id=TID, course_code=code, course_name=name, credit=4,
                   version=1, status="ENABLED")
    db.add(row)
    db.flush()
    return row


def _file(db, *, owner=100, name="原校成绩单.pdf", digest="a" * 64,
          scan="CLEAN", status="AVAILABLE"):
    from app.models.file import FileObject

    row = FileObject(
        tenant_id=TID, file_key=f"recog/{name}-{digest[:8]}", file_name=name, ext="pdf",
        mime_type="application/pdf", size_bytes=2048, sha256=digest,
        biz_type="TEMP_PRIVATE", biz_id=None, visibility="PRIVATE",
        security_level="INTERNAL", status=status, storage_backend="local",
        storage_zone="ACTIVE" if status == "AVAILABLE" else "QUARANTINE",
        upload_source="USER", owner_user_id=int(owner), created_by=int(owner),
        scan_required=scan != "NOT_REQUIRED", scan_status=scan,
        available_at=datetime.utcnow() if status == "AVAILABLE" else None,
    )
    db.add(row)
    db.flush()
    return row


def _body(course, file_ids=(), score=85):
    return SimpleNamespace(
        sourceCourseName="原校高等数学", sourceScore=score, sourceCredit=4,
        sourceOrigin="转学前原校", targetCourseId=str(course.id),
        attachmentFileIds=[str(v) for v in file_ids], reason="转学课程替代",
    )


@pytest.fixture()
def recog(db_mode):
    from app.modules.academic_affairs.services import (
        academic_affairs_recognition_public_service as svc,
    )

    return svc


def test_submit_binds_attachments_and_freezes_manifest(recog, db_mode):
    """佐证必须真的走文件中心建出 ACTIVE 绑定并冻结清单，不是记一串 fileId。"""
    from app.models import AaGradeRecognition
    from app.models.file import FileBinding

    db = _session()
    student = _student(db)
    course = _course(db)
    evidence_file = _file(db)
    db.commit()
    file_id, course_obj_id = evidence_file.id, course.id
    db.close()

    _ctx(student_id=None)
    result = recog.submit(None, _body(SimpleNamespace(id=course_obj_id), [file_id]))
    assert result["status"] == "SUBMITTED"

    db = _session()
    row = db.query(AaGradeRecognition).filter(AaGradeRecognition.tenant_id == TID).one()
    assert row.evidence_manifest_hash, "认定申请没有冻结证据清单哈希"
    binding = db.query(FileBinding).filter(
        FileBinding.tenant_id == TID, FileBinding.file_id == int(file_id)).one()
    assert binding.status == "ACTIVE" and binding.is_current
    assert binding.biz_type == "AA_RECOGNITION" and str(binding.biz_id) == str(row.id)
    db.close()


def test_cannot_use_another_students_file_as_recognition_evidence(recog, db_mode):
    """同租户里知道别人的 fileId 也不行——认定和免修共用同一套归属校验。"""
    from app.core.exceptions import AppException
    from app.models import AaGradeRecognition

    db = _session()
    _student(db, "RG1001", "别人")
    student = _student(db, "RG2401")
    course = _course(db)
    victim_file = _file(db, owner=999, name="别人的成绩单.pdf", digest="b" * 64)
    db.commit()
    file_id, course_id = victim_file.id, course.id
    db.close()

    _ctx()
    with pytest.raises(AppException):
        recog.submit(None, _body(SimpleNamespace(id=course_id), [file_id]))

    db = _session()
    assert db.query(AaGradeRecognition).filter(
        AaGradeRecognition.tenant_id == TID).count() == 0, "被拒的申请不该留下半条记录"
    db.close()


def test_quarantined_file_cannot_become_recognition_evidence(recog, db_mode):
    from app.core.exceptions import AppException

    db = _session()
    _student(db)
    course = _course(db)
    pending = _file(db, name="扫描中.pdf", digest="c" * 64, scan="PENDING", status="QUARANTINED")
    db.commit()
    file_id, course_id = pending.id, course.id
    db.close()

    _ctx()
    with pytest.raises(AppException) as exc:
        recog.submit(None, _body(SimpleNamespace(id=course_id), [file_id]))
    assert exc.value.code == "FILE_NOT_READY"


def _submitted(db_ids):
    """提交一条带佐证的认定申请，返回 recognitionId。"""
    from app.modules.academic_affairs.services import (
        academic_affairs_recognition_public_service as svc,
    )

    _ctx()
    return svc.submit(None, _body(SimpleNamespace(id=db_ids["course"]), [db_ids["file"]]))["recognitionId"]


def _base_ids():
    db = _session()
    student = _student(db)
    course = _course(db)
    evidence_file = _file(db)
    db.commit()
    ids = {"student": student.id, "course": course.id, "file": evidence_file.id}
    db.close()
    return ids


def test_approve_rejects_when_evidence_replaced_after_submission(recog, db_mode):
    """审批期间佐证内容被换掉 → 终审必须拒绝发学分。"""
    from app.core.exceptions import AppException
    from app.models import AcademicGrade
    from app.models.file import FileObject

    ids = _base_ids()
    rid = _submitted(ids)

    db = _session()
    file_obj = db.get(FileObject, int(ids["file"]))
    file_obj.sha256 = "d" * 64
    db.commit()
    db.close()

    admin = {"userId": "1", "currentRoleCode": "ACADEMIC_ADMIN"}
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "currentRoleCode": "ACADEMIC_ADMIN",
                      "realName": "教务处", "activeContextId": "ctx"})
    with pytest.raises(AppException) as exc:
        recog.review(admin, rid, "APPROVE")
    assert exc.value.http_status == 409 and "EVIDENCE_INVALIDATED" in exc.value.message

    db = _session()
    assert db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == TID,
        AcademicGrade.source_biz_type == "RECOGNITION").count() == 0, "证据失效却仍生成了正式成绩"
    db.close()


def test_approve_with_intact_evidence_creates_one_formal_grade(recog, db_mode):
    """证据完好时终审必须成功，并生成唯一一条带来源回链的正式成绩。"""
    from app.core.context import set_current_user, set_tenant
    from app.models import AcademicGrade

    ids = _base_ids()
    rid = _submitted(ids)

    set_tenant({"tenantId": str(TID)})
    set_current_user({"userId": "1", "tenantId": str(TID), "currentRoleCode": "ACADEMIC_ADMIN",
                      "realName": "教务处", "activeContextId": "ctx"})
    result = recog.review({"userId": "1", "currentRoleCode": "ACADEMIC_ADMIN"}, rid, "APPROVE")
    assert result["status"] == "APPROVED"

    db = _session()
    grades = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == TID,
        AcademicGrade.source_biz_type == "RECOGNITION").all()
    assert len(grades) == 1
    assert grades[0].pass_status == "PASSED" and int(grades[0].attempt_no) == 1
    assert int(grades[0].source_biz_id) == int(rid)
    db.close()


def test_concurrent_submit_cannot_create_two_live_applications(recog, db_mode):
    """两个并发提交只能落一条在途申请——否则两条各自终审就是两个正式 PASSED。"""
    from app.core.exceptions import AppException
    from app.models import AaGradeRecognition

    ids = _base_ids()
    db = _session()
    second_file = _file(db, name="第二份.pdf", digest="e" * 64)
    db.commit()
    second_id = second_file.id
    db.close()

    ok, failed = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def _worker(file_id):
        _ctx()
        try:
            barrier.wait(timeout=30)
            result = recog.submit(None, _body(SimpleNamespace(id=ids["course"]), [file_id]))
            with lock:
                ok.append(result["recognitionId"])
        except AppException as exc:
            with lock:
                failed.append((exc.http_status, exc.code))
        except Exception as exc:  # noqa: BLE001
            with lock:
                failed.append((None, repr(exc)))

    threads = [threading.Thread(target=_worker, args=(ids["file"],)),
               threading.Thread(target=_worker, args=(second_id,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=90)

    assert len(ok) == 1, f"两个并发提交都落库了：成功={ok} 失败={failed}"
    assert len(failed) == 1, f"另一个提交没有被拒：{failed}"

    db = _session()
    live = db.query(AaGradeRecognition).filter(
        AaGradeRecognition.tenant_id == TID,
        AaGradeRecognition.status.in_(("SUBMITTED", "APPROVED"))).all()
    assert len(live) == 1, f"同一学生同一目标课程出现 {len(live)} 条在途/通过认定"
    db.close()


def test_recognition_is_wired_to_shared_evidence_guard_and_locked_allocator():
    """认定必须共用免修那套证据守卫和加锁分配器，不能自己另写一份。"""
    import inspect

    import app.models  # noqa: F401
    from app.modules.academic_affairs.services import (
        academic_affairs_exemption_evidence_service as evidence,
        academic_affairs_recognition_public_service as recog_svc,
    )

    submit_src = inspect.getsource(recog_svc.submit)
    review_src = inspect.getsource(recog_svc.review)
    assert "with_for_update()" in submit_src, "submit 查重前没有对学生主档行取互斥锁"
    assert "_fresh_read(" in submit_src, "查重仍是普通读，看不见并发提交刚落库的申请"
    assert "freeze_manifest" in submit_src, "submit 没有冻结证据清单"
    assert "require_valid_manifest" in review_src, "终审没有复验证据"
    assert "lock_grade_identity" in review_src, "终审没有取成绩身份锁"
    # 复验必须早于正式成绩写入
    assert review_src.index("require_valid_manifest") < review_src.index("AcademicGrade(")
    # 免修与认定共用同一套守卫
    assert {"EXEMPTION", "RECOGNITION"} <= set(evidence._KINDS)
