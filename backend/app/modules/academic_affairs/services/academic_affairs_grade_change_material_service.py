"""Correction material bindings reuse the formal file/evidence owners."""
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import StudentProfile
from app.models.file import FileBinding, FileObject
from app.services.db_service import _tid
from . import academic_affairs_exemption_evidence_service as evidence


def freeze(db, request, user, file_ids):
    student = db.scalar(select(StudentProfile).where(
        StudentProfile.id == request.student_id, StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if student is None:
        raise not_found("成绩学生不存在，无法登记更正材料")
    ids = [str(value) for value in file_ids or []]
    if len(ids) > 8 or any(not value.isdigit() or int(value) <= 0 for value in ids) or len(set(ids)) != len(ids):
        raise AppException("VALIDATION_ERROR", "更正材料编号无效或重复")
    result = evidence.freeze_manifest(db, request, sorted(ids, key=int), actor=user, student=student,
                                      kind="GRADE_CHANGE", scope={"gradeTaskId": str(request.grade_task_id)})
    if any(len(str(entry.get("sha256") or "")) != 64 for entry in result["entries"]):
        raise AppException("VALIDATION_ERROR", "材料尚无完整内容校验值，请待文件中心完成登记后重试")
    return result


def verify(db, request, *, lock=False):
    if lock:
        # Same order as the file binding owner: file rows, then binding rows.
        entries = evidence.load_manifest(request)
        file_ids = sorted({int(e["fileId"]) for e in entries
                           if isinstance(e, dict) and str(e.get("fileId", "")).isdigit()})
        binding_ids = sorted({int(e["bindingId"]) for e in entries
                              if isinstance(e, dict) and str(e.get("bindingId", "")).isdigit()})
        for model, ids in ((FileObject, file_ids), (FileBinding, binding_ids)):
            if ids:
                db.scalars(select(model).where(model.id.in_(ids), model.tenant_id == _tid())
                           .order_by(model.id).with_for_update().execution_options(populate_existing=True)).all()
    result = evidence.verify_manifest(db, request, kind="GRADE_CHANGE")
    binding_ids = [int(e["bindingId"]) for e in result["entries"]
                   if isinstance(e, dict) and str(e.get("bindingId", "")).isdigit()]
    bindings = {b.id: b for b in db.scalars(select(FileBinding).where(
        FileBinding.id.in_(binding_ids), FileBinding.tenant_id == _tid(),
    )).all()} if binding_ids else {}
    for entry in result["entries"]:
        if not isinstance(entry, dict) or not str(entry.get("bindingId", "")).isdigit():
            continue
        binding = bindings.get(int(entry["bindingId"]))
        if (not binding or binding.module_code != "ACADEMIC_AFFAIRS"
                or binding.relation_type != "GRADE_CHANGE_EVIDENCE"
                or binding.subject_type != "STUDENT" or str(binding.subject_id) != str(request.student_id)
                or binding.student_id != request.student_id):
            result["problems"].append("更正材料的业务用途或学生身份与原申请不一致")
        if len(str(entry.get("sha256") or "")) != 64:
            result["problems"].append("更正材料缺少完整内容校验值")
    return result


def require_valid(db, request):
    result = verify(db, request, lock=True)
    if result["problems"]:
        raise AppException("DATA_CONFLICT", "更正材料已失效，请驳回补正：" + "；".join(result["problems"][:5]), http_status=409)


def details(db, request):
    result = verify(db, request)
    files = [{"fileId": str(e["fileId"]), "fileName": e.get("fileName"), "sha256": e.get("sha256"),
              "bindingId": str(e["bindingId"]), "frozenFileObjectVersion": e.get("fileVersion"),
              "boundAt": e.get("boundAt")} for e in result["entries"]
             if isinstance(e, dict) and str(e.get("fileId", "")).isdigit() and str(e.get("bindingId", "")).isdigit()]
    return {"evidenceManifestHash": result["manifestHash"], "evidenceFiles": files,
            "evidenceProblems": result["problems"],
            "evidenceState": "INVALID" if result["problems"] else "VALID" if files else "EMPTY"}


def file_access(db, file_obj, bindings, user, action):
    if db is None or action not in {"meta", "preview", "download"}:
        return False
    from . import academic_affairs_grade_change_read_service as changes
    from app.models.academic_affairs_effective_grade import AaGradeChangeRequest

    active = [b for b in bindings if not b.is_deleted and b.status == "ACTIVE" and b.is_current
              and b.biz_type == "AA_GRADE_CHANGE_REQUEST" and b.relation_type == "GRADE_CHANGE_EVIDENCE"
              and b.module_code == "ACADEMIC_AFFAIRS" and str(b.biz_id).isdigit()]
    if not active:
        return False
    try:
        access = changes._access(db, user)
        requests = db.execute(changes._query(db, user, access).where(
            AaGradeChangeRequest.id.in_([int(b.biz_id) for b in active]),
        )).all()
    except AppException:
        return False
    for row in requests:
        request = row[0]
        for entry in evidence.load_manifest(request):
            if not isinstance(entry, dict) or str(entry.get("fileId")) != str(file_obj.id):
                continue
            if any(str(b.id) == str(entry.get("bindingId")) and str(b.biz_id) == str(request.id)
                   and str(b.student_id) == str(request.student_id) for b in active):
                return not verify(db, request)["problems"]
    return False
