#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(
    str(ROOT / "scripts/maintenance/fix_abcd_regression_contracts_round3.py"),
    run_name="__main__",
)


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) < count:
        raise SystemExit(f"round4 expected snippet not found: {path}\n---\n{old[:600]}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")
    print(f"round4 patched {path}")


# UnifiedMessage 没有 source_biz_type 字段。业务事件写入已有 action_key；
# 历史消息的无动作兜底只能安全使用现存 source_module + source_biz_id。
replace(
    "backend/app/services/affairs_student_contract_service.py",
    '''            if not key:
                key, defaults = _default_action(row.source_biz_type, row.source_biz_id)
                params = {**defaults, **params}
            item["actionKey"] = key
            item["actionParams"] = params
            item["recordId"] = str(row.source_biz_id or "")
            item["bizType"] = _biz(row.source_biz_type)
''',
    '''            biz_type = getattr(row, "source_biz_type", None) or row.source_module
            if not key:
                key, defaults = _default_action(biz_type, row.source_biz_id)
                params = {**defaults, **params}
            item["actionKey"] = key
            item["actionParams"] = params
            item["recordId"] = str(row.source_biz_id or "")
            item["bizType"] = _biz(biz_type)
''',
)
replace(
    "backend/app/services/affairs_student_contract_service.py",
    '''                    if row and not row.is_deleted and row.tenant_id == _tid():
                        key, defaults = _default_action(row.source_biz_type, row.source_biz_id)
''',
    '''                    if row and not row.is_deleted and row.tenant_id == _tid():
                        biz_type = getattr(row, "source_biz_type", None) or row.source_module
                        key, defaults = _default_action(biz_type, row.source_biz_id)
''',
)

# 发布接口是“受理 + 异步作业”。测试显式排空当前租户投递作业，
# 不再依赖 inline claim 的时序，随后验证学生读侧与偏好过滤。
replace(
    "backend/tests/test_mobile_wave10.py",
    '''def test_notify_publish_class_scope_and_student_receives(client, db_mode):
''',
    '''def _drain_message_delivery_jobs():
    from app.core.context import set_tenant
    from app.services.message_delivery_service import claim_and_process_delivery_jobs
    set_tenant({"tenantId": str(MAIN)})
    try:
        for _ in range(3):
            if claim_and_process_delivery_jobs(limit=20, worker_id="test-notify-drain") == 0:
                break
    finally:
        set_tenant(None)


def test_notify_publish_class_scope_and_student_receives(client, db_mode):
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    assert r["code"] == 0 and r["data"]["recipientCount"] == 2
    stu_hdr = _notify_student_token(client, cid)
''',
    '''    assert r["code"] == 0 and r["data"]["recipientCount"] == 2, r
    _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
''',
)
replace(
    "backend/tests/test_mobile_wave10.py",
    '''    client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
               json={"title": "偏好测试通知", "content": "用于验证通知开关真实生效", "scopeType": "CLASS", "classId": cid})
    stu_hdr = _notify_student_token(client, cid)
''',
    '''    published = client.post("/api/v1/mobile/teacher/notify/publish", headers=hdr,
               json={"title": "偏好测试通知", "content": "用于验证通知开关真实生效", "scopeType": "CLASS", "classId": cid}).json()
    assert published["code"] == 0, published
    _drain_message_delivery_jobs()
    stu_hdr = _notify_student_token(client, cid)
''',
)

print("ABCD D-stage notification closure patch complete")
