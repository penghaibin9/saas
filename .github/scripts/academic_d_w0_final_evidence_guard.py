from pathlib import Path

path = Path("backend/app/modules/academic_affairs/services/academic_affairs_graduation_immutable_service.py")
source = path.read_text(encoding="utf-8")
old = '''        if str(run.overall or "").upper() != "SYSTEM_PASSED":\n            raise AppException(\n                "DATA_CONFLICT",\n                "最新正式毕业评估仍为 SYSTEM_ABNORMAL；普通教务终审禁止用审核备注覆盖评估结论，请先治理阻断项并重新预审",\n                http_status=409,\n            )\n        existing = db.scalars(select(GraduationDecisionFact).where(\n'''
new = '''        if str(run.overall or "").upper() != "SYSTEM_PASSED":\n            raise AppException(\n                "DATA_CONFLICT",\n                "最新正式毕业评估仍为 SYSTEM_ABNORMAL；普通教务终审禁止用审核备注覆盖评估结论，请先治理阻断项并重新预审",\n                http_status=409,\n            )\n        try:\n            run_items = json.loads(run.item_results_json or "[]")\n        except (TypeError, ValueError, json.JSONDecodeError):\n            run_items = []\n        if not isinstance(run_items, list) or _strict_overall(run_items) != "SYSTEM_PASSED":\n            raise AppException(\n                "DATA_CONFLICT",\n                "最新正式毕业评估 Run 的必需证据集合不完整或不满足当前 fail-closed 合同，禁止终审；请重新预审生成完整正式 Run",\n                http_status=409,\n            )\n        existing = db.scalars(select(GraduationDecisionFact).where(\n'''
if source.count(old) != 1:
    raise SystemExit(f"expected one academic_final insertion point, found {source.count(old)}")
patched = source.replace(old, new, 1)
for token in (
    'run_items = json.loads(run.item_results_json or "[]")',
    '_strict_overall(run_items) != "SYSTEM_PASSED"',
    '必需证据集合不完整',
):
    if token not in patched:
        raise SystemExit(f"missing token after patch: {token}")
path.write_text(patched.rstrip() + "\n", encoding="utf-8")
print("D-W0 academic_final immutable evidence completeness guard applied")
