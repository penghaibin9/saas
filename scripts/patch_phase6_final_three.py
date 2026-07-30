from __future__ import annotations

import subprocess
from pathlib import Path

BRANCH = "audit/file-capability-inventory"
ROOT = Path(__file__).resolve().parents[1]
subprocess.run(["git", "fetch", "origin", BRANCH], check=True)
subprocess.run(["git", "checkout", "-B", "stage6-final-three", f"origin/{BRANCH}"], check=True)


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/tests/test_graduation_material_center_phase6.py",
    '    assert registry.index("graduation_material_center.router") < registry.index("graduation_sensitive_router.router")\n',
    '    assert registry.index("graduation_sensitive_router.router") < registry.index("api_router.include_router(graduation.router")\n'
    '    assert registry.index("api_router.include_router(graduation.router") < registry.index("graduation_material_center.router")\n',
)

replace_once(
    "backend/tests/graduation_material_center_mysql_acceptance.py",
    '''        proposal_v2.defense_result = "PASS"
        proposal_v2.defense_comment = "开题答辩通过"
        proposal_v2.defense_at = datetime.utcnow()
        db.commit()
''',
    '''        proposal_v2.defense_result = "PASS"
        proposal_v2.defense_comment = "开题答辩通过"
        proposal_v2.defense_at = datetime.utcnow()
        # 真实业务只有进入成果检查阶段后才允许提交初稿；测试夹具必须推进
        # 学生流程状态，不能通过放宽生产状态机来证明文件链可用。
        db.get(GraduationStudent, student_id).stage = "FINAL_CHECK"
        db.commit()
''',
)

replace_once(
    "backend/app/modules/graduation/services/graduation_mobile_teacher_service.py",
    '''    from app.modules.graduation.services import graduation_service as svc
    detail = svc.get_proposal_detail(proposal_id)
    content = detail.get("content") or {}
    return {
        "id": str(detail.get("id") or proposal_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "version": detail.get("version") or "", "isResubmit": bool(detail.get("isResubmit")),
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "background": content.get("background") or "",
        "plan": content.get("plan") or "", "outcome": content.get("outcome") or "",
        "reviewComment": detail.get("reviewComment") or "",
        "attachments": int(detail.get("attachments") or 0),
        "attachmentsList": detail.get("attachmentsList") or [], "versions": detail.get("versions") or [],
    }
''',
    '''    from app.modules.graduation.services import graduation_material_center_service as center
    detail = center.proposal_detail(int(proposal_id))
    content = detail.get("content") or {}
    safe_versions = detail.get("currentSafeVersions") or []
    attachments = [
        {**item, "downloadUrl": f"/api/v1/graduation/materials/{item['fileId']}/download"}
        for item in safe_versions
        if str(item.get("materialCode") or "").startswith("PROPOSAL_ATTACHMENT_")
    ]
    return {
        "id": str(detail.get("id") or proposal_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "version": detail.get("version") or "", "isResubmit": bool(detail.get("isResubmit")),
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "background": content.get("background") or "",
        "plan": content.get("plan") or "", "outcome": content.get("outcome") or "",
        "reviewComment": detail.get("reviewComment") or "",
        "attachments": len(attachments), "attachmentsList": attachments,
        "versions": detail.get("versions") or [], "currentSafeVersions": safe_versions,
        "reviewReady": bool(detail.get("reviewReady")),
    }
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_mobile_teacher_service.py",
    '''    from app.modules.graduation.services import graduation_service as svc
    return svc.review_proposal(proposal_id, action, comment)
''',
    '''    from app.modules.graduation.services import graduation_material_center_service as center
    return center.review_proposal(int(proposal_id), action, comment, user)
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_mobile_teacher_service.py",
    '''    from app.modules.graduation.services import graduation_service as svc
    detail = svc.get_final_detail(final_id)
    return {
        "id": str(detail.get("id") or final_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "type": detail.get("type") or "", "version": detail.get("version") or "",
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "plagiarismRate": detail.get("plagiarismRate") or "—",
        "plagiarismStatus": detail.get("plagiarismStatus") or "未检测",
        "plagiarismTone": detail.get("plagiarismTone") or "success",
        "reviewComment": detail.get("reviewComment") or "",
        "attachmentsList": detail.get("attachmentsList") or [], "versions": detail.get("versions") or [],
    }
''',
    '''    from app.modules.graduation.services import graduation_material_center_service as center
    detail = center.final_detail(int(final_id))
    safe_versions = detail.get("currentSafeVersions") or []
    attachments = [
        {**item, "downloadUrl": f"/api/v1/graduation/materials/{item['fileId']}/download"}
        for item in safe_versions
    ]
    return {
        "id": str(detail.get("id") or final_id), "studentName": detail.get("studentName") or "",
        "className": detail.get("className") or "", "topicTitle": detail.get("topicTitle") or "",
        "type": detail.get("type") or "", "version": detail.get("version") or "",
        "submitAt": detail.get("submitAt") or "", "status": detail.get("status"),
        "statusLabel": detail.get("statusLabel"), "plagiarismRate": detail.get("plagiarismRate") or "—",
        "plagiarismStatus": detail.get("plagiarismStatus") or "未检测",
        "plagiarismTone": detail.get("plagiarismTone") or "success",
        "reviewComment": detail.get("reviewComment") or "",
        "attachmentsList": attachments, "versions": detail.get("versions") or [],
        "currentSafeVersions": safe_versions, "reviewReady": bool(detail.get("reviewReady")),
    }
''',
)
replace_once(
    "backend/app/modules/graduation/services/graduation_mobile_teacher_service.py",
    '''    from app.modules.graduation.services import graduation_service as svc
    return svc.review_final(final_id, action, comment)
''',
    '''    from app.modules.graduation.services import graduation_material_center_service as center
    return center.review_final(int(final_id), action, comment, user)
''',
)

print("Stage 6 final three fixes applied")
