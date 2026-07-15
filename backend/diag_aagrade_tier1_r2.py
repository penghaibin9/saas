"""成绩管理 Tier1 R2（成绩导入/成绩导出/成绩统计）—— 独立 SQLite 自测脚本（不连共享 MySQL）。

用法：VENV_PYTHON diag_aagrade_tier1_r2.py
仅用于本轮子智能体自测证据留存，非正式 pytest 回归（正式 MySQL 回归由总控事后统一执行）。
覆盖：
  1) 成绩导入：模板下载 / dry-run 预校验（合法行+5类错误行）/ 确认导入（含 0 分边界）/ 记录回显 /
     状态不可写时拒绝导入 / 未通过预校验禁止确认
  2) 成绩导出：学生成绩单 xlsx（用途<5字→400，≥5字→200 且内容非空）
  3) 成绩统计：/stats/grade + /stats/grade/detail + /stats/export(domain=grade) 三级模块「成绩管理→成绩统计」
     复用既有教务统计聚合，回归验证未被本轮改动破坏
"""
from __future__ import annotations

import io
import os
import sys

os.environ["APP_ENV"] = "test"
os.environ["DB_ENABLED"] = "true"
# C: 盘本机环境磁盘几乎写满（df 显示可用 <100MB，与本次改动无关的预置环境问题），
# 自测库改落 D: 盘规避 "No space left on device"，仅影响本地自测文件位置，不改变被测代码路径。
_DB_PATH = "D:/claude_scratch_aagrade/diag_aagrade_tier1_r2.db"
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["TEST_DATABASE_URL"] = f"sqlite+pysqlite:///{_DB_PATH}"
os.environ["MOCK_LOGIN_ENABLED"] = "true"

if os.path.exists(_DB_PATH):
    os.remove(_DB_PATH)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

from app.db.base import metadata  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402

engine = get_engine()
metadata.create_all(bind=engine)
print("[1] metadata.create_all OK（无新表，复用既有 t_aa_grade_task/t_aa_grade_record/t_acad_grade）")

TID = 1000000000000000001  # school_admin01 mock-login 默认租户（对齐 tenant_context._MOCK_TENANTS "demo"）

from app.models import College, Major, StudentProfile  # noqa: E402

db = get_sessionmaker()()
college = College(tenant_id=TID, college_name="软件学院", code="RJ", status="ACTIVE")
db.add(college)
db.flush()
major = Major(tenant_id=TID, college_id=college.id, major_name="软件技术", code="RJ01")
db.add(major)
db.flush()

students = []
for i in range(3):
    s = StudentProfile(tenant_id=TID, student_no=f"GR{i:04d}", real_name=f"成绩学生{i}",
                       current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE",
                       college_id=college.id, major_id=major.id)
    db.add(s)
    students.append(s)
db.flush()
db.commit()
student_ids = [s.id for s in students]
student_nos = [s.student_no for s in students]
db.close()
print(f"[2] 种子数据写入 OK（3 学生：{student_nos}）")

login = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"})
assert login.status_code == 200, f"mock-login 失败: {login.status_code} {login.text}"
token = login.json()["data"]["accessToken"]
H = {"Authorization": f"Bearer {token}"}
print("[3] mock-login(school_admin01) OK")

results = []


def check(name, method, path, expect_status=200, expect_keys=None, params=None, body=None,
         headers=H, files=None, raw=False):
    fn = {"GET": client.get, "POST": client.post}[method]
    kwargs = {"headers": headers} if headers else {}
    if params is not None:
        kwargs["params"] = params
    if files is not None:
        kwargs["files"] = files
    elif body is not None:
        kwargs["json"] = body
    r = fn(path, **kwargs)
    ok = r.status_code == expect_status
    detail = ""
    data = None
    if ok and not raw:
        try:
            data = r.json().get("data")
            if expect_keys:
                missing = [k for k in expect_keys if k not in (data or {})]
                if missing:
                    ok = False
                    detail = f"missing keys {missing} in {data}"
        except Exception as e:  # noqa: BLE001
            ok = False
            detail = f"parse error: {e}"
    if not ok and not detail:
        detail = r.text[:300]
    results.append((name, ok, r.status_code, detail))
    print(f"  {'OK ' if ok else 'FAIL'} {name} [{r.status_code}] {detail}")
    return r, data


print("[4] 建成绩录入任务（平时30/期末70/及格线60）：")
r, task = check("创建任务", "POST", "/api/v1/academic-affairs/grade-tasks", 200,
                ["gradeTaskId", "status"], body={
                    "courseName": "数据结构", "termCode": "2025-2026", "credit": 4,
                    "usualRatio": 30, "finalRatio": 70, "passLine": 60})
task_id = task["gradeTaskId"]
assert task["status"] == "NOT_STARTED"

print("[5] 成绩批量导入 —— 下载模板：")
tpl = client.get(f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/template", headers=H)
ok = tpl.status_code == 200 and len(tpl.content) > 0 and tpl.headers.get("content-type", "").startswith(
    "application/vnd.openxmlformats")
results.append(("下载导入模板", ok, tpl.status_code, "" if ok else tpl.text[:200]))
print(f"  {'OK ' if ok else 'FAIL'} 下载导入模板 [{tpl.status_code}] bytes={len(tpl.content)}")


def build_xlsx(rows):
    """rows: list[list] 与 IMPORT_HEADERS 顺序一致：学号/姓名/平时分/期末分/异常标记。"""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "导入模板"
    ws.append(["学号 *", "姓名", "平时分", "期末分", "异常标记"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


print("[6] 成绩批量导入 —— dry-run 预校验（3 合法行含 0 分边界 + 5 错误行）：")
rows = [
    [student_nos[0], "成绩学生0", 85, 90, ""],       # 合法：正常合成
    [student_nos[1], "成绩学生1", 0, 60, ""],         # 合法：0 分边界（回归此前 `or None` 假阳性 bug）
    [student_nos[2], "成绩学生2", "", "", "缺考"],    # 合法：异常标记，分数留空
    ["", "无学号", 80, 80, ""],                       # 错误：学号必填
    ["NOEXIST0001", "查无此人", 80, 80, ""],          # 错误：未匹配到学生
    [student_nos[0], "成绩学生0", 80, 80, ""],        # 错误：文件内学号重复（与第1行重复）
    [student_nos[1], "成绩学生1", 150, 80, ""],       # 错误：平时分越界
    [student_nos[2], "成绩学生2", 80, 80, "旷考"],    # 错误：异常标记非法
]
content = build_xlsx(rows)
up = client.post(f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/xlsx", headers=H,
                 files={"file": ("成绩导入.xlsx", content,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
up_ok = up.status_code == 200
up_data = up.json().get("data") if up_ok else None
if up_ok:
    up_ok = (up_data["total"] == 8 and up_data["validRows"] == 3 and up_data["invalidRows"] == 5)
results.append(("dry-run 8 行(3 合法/5 错误)", up_ok, up.status_code,
                "" if up_ok else f"got={up_data}"))
print(f"  {'OK ' if up_ok else 'FAIL'} dry-run 8 行(3 合法/5 错误) [{up.status_code}] {up_data if not up_ok else ''}")
assert up_ok, "dry-run 校验结果不符预期，停止后续步骤"
pre_rows = up_data["rows"]
pre_errors = up_data["errors"]
print(f"     错误明细：{[(e['rowNo'], e['field']) for e in pre_errors]}")

print("[7] 成绩批量导入 —— 错误行仍未通过时确认导入应 409：")
check("未修正即确认导入应 409(DATA_CONFLICT)", "POST",
     f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/confirm", 409,
     body={"rows": pre_rows})

print("[8] 成绩批量导入 —— 下载错误行 xlsx：")
err_resp = client.post(f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/errors-xlsx", headers=H,
                       json={"rows": pre_rows, "errors": pre_errors})
err_ok = err_resp.status_code == 200 and len(err_resp.content) > 0
results.append(("下载错误行 xlsx", err_ok, err_resp.status_code, ""))
print(f"  {'OK ' if err_ok else 'FAIL'} 下载错误行 xlsx [{err_resp.status_code}] bytes={len(err_resp.content)}")

print("[9] 成绩批量导入 —— 仅提交 3 条合法行确认导入：")
valid_rows = [r for r, e in zip(pre_rows, [0, 0, 0, 1, 1, 1, 1, 1]) if e == 0]
assert len(valid_rows) == 3
r, confirm_data = check("确认导入 3 条合法行", "POST",
                        f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/confirm", 200,
                        ["created", "imported"], body={"rows": valid_rows})
assert confirm_data["created"] == 3, f"期望导入 3 条，实得 {confirm_data}"

print("[10] 成绩批量导入 —— 记录回显（校验 0 分未被误判为空，且总评正确合成）：")
r, recs = check("成绩录入表当前已录状态", "GET",
                f"/api/v1/academic-affairs/grade-tasks/{task_id}/records", 200, ["items"])
by_no = {}
stu_no_by_id = dict(zip([str(x) for x in student_ids], student_nos))
for it in recs["items"]:
    by_no[stu_no_by_id.get(it["studentId"], it["studentId"])] = it
s0 = by_no[student_nos[0]]
s1 = by_no[student_nos[1]]
s2 = by_no[student_nos[2]]
assert s0["usualScore"] == 85 and s0["finalScore"] == 90, f"学生0 分数不符：{s0}"
assert s0["totalScore"] == round(85 * 0.3 + 90 * 0.7), f"学生0 总评合成错误：{s0}"
assert s1["usualScore"] == 0, f"学生1 平时分应为 0（非 None，回归 `or None` bug）：{s1}"
assert s1["totalScore"] == round(0 * 0.3 + 60 * 0.7), f"学生1 总评合成错误：{s1}"
assert s2["exceptionFlag"] == "ABSENT" and s2["totalScore"] is None, f"学生2 异常标记/总评不符：{s2}"
print("  OK  0 分边界未被 `or None` 误判 + 总评合成正确 + 异常标记正确写入")
results.append(("0分边界+总评合成+异常标记回显", True, 200, ""))

print("[11] 提交任务后（不可写状态）应拒绝再次导入：")
check("提交任务", "POST", f"/api/v1/academic-affairs/grade-tasks/{task_id}/submit", 200, ["status"])
content2 = build_xlsx([[student_nos[0], "成绩学生0", 60, 60, ""]])
up2 = client.post(f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/xlsx", headers=H,
                  files={"file": ("x.xlsx", content2,
                                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
up2_ok = up2.status_code == 409
results.append(("SUBMITTED 状态下导入应 409", up2_ok, up2.status_code, "" if up2_ok else up2.text[:200]))
print(f"  {'OK ' if up2_ok else 'FAIL'} SUBMITTED 状态下导入应 409 [{up2.status_code}]")

print("[12] 走完整审核发布链路，供成绩导出/成绩统计取数（读侧仅认 PUBLISHED 投影）：")
check("学院审核通过", "POST", f"/api/v1/academic-affairs/grade-tasks/{task_id}/college-review", 200,
     body={"action": "APPROVE"})
check("教务终审发布", "POST", f"/api/v1/academic-affairs/grade-tasks/{task_id}/publish", 200,
     ["status", "projected", "failCount"])

print("[13] 成绩导出 —— 学生成绩单 xlsx（用途<5字应 400，≥5字应 200 且非空）：")
sid0 = student_ids[0]
check("导出用途过短应 400", "POST", f"/api/v1/academic-affairs/students/{sid0}/transcript/export", 400,
     body={"purpose": "短"})
exp = client.post(f"/api/v1/academic-affairs/students/{sid0}/transcript/export", headers=H,
                  json={"purpose": "自测导出成绩单验证"})
exp_ok = exp.status_code == 200 and len(exp.content) > 0
results.append(("导出成绩单 xlsx", exp_ok, exp.status_code, ""))
print(f"  {'OK ' if exp_ok else 'FAIL'} 导出成绩单 xlsx [{exp.status_code}] bytes={len(exp.content)}")

print("[14] 无 token 访问导入/导出端点应 401（权限门禁未被绕过）：")
check("无 token 下载模板应 401", "GET", f"/api/v1/academic-affairs/grade-tasks/{task_id}/import/template",
     401, headers=None)
check("无 token 导出成绩单应 401", "POST", f"/api/v1/academic-affairs/students/{sid0}/transcript/export",
     401, body={"purpose": "无token测试用途"}, headers=None)

print("[15] 成绩统计（本轮复用既有 教务统计→成绩统计 聚合，回归确认未被破坏）：")
check("成绩统计聚合 /stats/grade", "GET", "/api/v1/academic-affairs/stats/grade", 200,
     ["failRate", "entryPublishRate", "makeupCount", "retakeCount"])
check("成绩统计下钻 /stats/grade/detail", "GET", "/api/v1/academic-affairs/stats/grade/detail", 200,
     params={"page": 1, "pageSize": 20})
check("成绩统计导出 /stats/export(domain=grade)", "POST", "/api/v1/academic-affairs/stats/export", 200,
     body={"domain": "grade", "purpose": "成绩统计导出自测"}, raw=True)

fail_count = sum(1 for _, ok, _, _ in results if not ok)
print(f"\n=== 汇总：{len(results)} 项检查，{len(results) - fail_count} 通过，{fail_count} 失败 ===")
if fail_count:
    sys.exit(1)
print("ALL PASS")
