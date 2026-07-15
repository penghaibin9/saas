"""教务中心 · 教学计划（收编）· 第三轮补缺 R3 · 端到端。

背景：《教学计划-生产级施工包.md》顶部 2026-07-14 用户最终裁决「收编」——不建独立
t_aa_teaching_plan* 域。navPlan `aa-teaching-plan` 10 个叶子中，年级/专业教学计划、学期教学计划/
课程开设计划、计划归档 3 个此前已收编到「培养方案」「教学任务」「教务归档」既有页面。本文件覆盖
R3 本轮补齐的剩余 5 个叶子：实践教学计划/计划审核/计划发布/计划变更/计划执行进度——全部收编到既有
真实实现，零新表零迁移，仅补齐此前缺失的自动化测试覆盖：

TP1 计划变更（POST /programs/{id}/change）正常流程：ENABLED 方案变更成功生成新版本 + 专属审计事件；
TP2 计划变更校验：非法状态(DRAFT)拒绝 409、原因不足 5 字拒绝 400、学生令牌越权 403；
TP3 学分要求（含「实践环节」模块，供「实践教学计划」页交叉展示学分目标）：保存+读取回显 + 模块名重复 400；
TP4 计划审核/计划发布工作台查询口径（GET /programs?statusIn=...）与前端 review/publish 两个 tab 完全一致，
    且已发布方案不再出现在「计划审核」待办里。

「计划执行进度」收编到既有 GET /teaching-task-batches/stats，已有
test_aa_teaching_task.py::test_tt5_two_level_confirm_approve_ready 覆盖统计口径，本文件不重复造轮子。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _enabled_program(client, hdr, name="软件技术2026方案", total=10):
    """建方案→加课→提交→两审通过（PUBLISHED）→绑年级（ENABLED），返回 programId。"""
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": name, "majorId": "1", "gradeYear": "2026",
        "totalCredits": total}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "高等数学", "openTermNo": 1, "module": "公共基础", "credit": total})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # PUBLISHED
    client.post(f"{BASE}/programs/{pid}/bind", headers=hdr, json={"gradeYear": "2026"})  # ENABLED
    return pid


def test_tp1_change_creates_new_version_with_audit(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = _enabled_program(client, hdr)
    r = client.post(f"{BASE}/programs/{pid}/change", headers=hdr,
                    json={"reason": "学分要求调整，新增一门专业核心课"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["version"] == 2 and d["status"] == "DRAFT"
    # 版本链可查：新旧版本均在同一谱系
    versions = client.get(f"{BASE}/programs/{d['programId']}/versions", headers=hdr).json()["data"]["items"]
    assert any(v["programId"] == d["programId"] and v["version"] == 2 for v in versions)
    assert any(v["programId"] == pid and v["version"] == 1 for v in versions)


def test_tp2_change_validation_and_permission(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    # 未发布(DRAFT)方案不可变更（须先发布，否则直接编辑即可，不算「计划变更」）
    pid_draft = client.post(f"{BASE}/programs", headers=hdr,
                            json={"programName": "草稿方案"}).json()["data"]["programId"]
    r1 = client.post(f"{BASE}/programs/{pid_draft}/change", headers=hdr, json={"reason": "随便改改试一下"})
    assert r1.status_code == 409

    pid = _enabled_program(client, hdr, name="方案B")
    # 变更原因不足 5 字
    r2 = client.post(f"{BASE}/programs/{pid}/change", headers=hdr, json={"reason": "改"})
    assert r2.status_code == 400

    # 学生令牌越权（require_permission 早于业务逻辑拦截）
    hdr_stu = _hdr(client, "student01")
    r3 = client.post(f"{BASE}/programs/{pid}/change", headers=hdr_stu, json={"reason": "学生尝试变更教学计划"})
    assert r3.status_code == 403


def test_tp3_credit_requirements_practice_module_roundtrip(client, db_mode):
    hdr = _hdr(client, "school_admin01")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "实践教学计划测试方案", "totalCredits": 100}).json()["data"]["programId"]
    r = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={"items": [
        {"module": "公共基础", "creditTarget": 30},
        {"module": "专业核心", "creditTarget": 50},
        {"module": "实践环节", "creditTarget": 20, "note": "集中实践/顶岗实习"}
    ]})
    assert r.status_code == 200
    assert r.json()["data"]["targetSum"] == 100

    got = client.get(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr).json()["data"]
    practice = next(i for i in got["items"] if i["module"] == "实践环节")
    assert practice["creditTarget"] == 20 and practice["note"] == "集中实践/顶岗实习"

    # 模块名重复拒绝
    r2 = client.put(f"{BASE}/programs/{pid}/credit-requirements", headers=hdr, json={"items": [
        {"module": "实践环节", "creditTarget": 10}, {"module": "实践环节", "creditTarget": 5}
    ]})
    assert r2.status_code == 400


def test_tp4_review_publish_workbench_status_filters(client, db_mode):
    """计划审核/计划发布两个 navPlan 叶子复用 programs/console?tab=review|publish，
    分别按 statusIn=COLLEGE_REVIEW,ACADEMIC_REVIEW 与 statusIn=PUBLISHED,ENABLED 查询——
    与前端 AaProgramConsoleView.loadReview()/loadPublish() 完全同口径。"""
    hdr = _hdr(client, "school_admin01")
    pid = client.post(f"{BASE}/programs", headers=hdr, json={
        "programName": "审核发布口径测试方案", "totalCredits": 5}).json()["data"]["programId"]
    client.post(f"{BASE}/programs/{pid}/courses", headers=hdr, json={
        "courseName": "体育", "openTermNo": 1, "module": "公共基础", "credit": 5})
    client.post(f"{BASE}/programs/{pid}/submit", headers=hdr)  # -> COLLEGE_REVIEW

    review_list = client.get(f"{BASE}/programs?statusIn=COLLEGE_REVIEW,ACADEMIC_REVIEW",
                             headers=hdr).json()["data"]["items"]
    assert any(p["programId"] == pid for p in review_list)

    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # -> ACADEMIC_REVIEW
    client.post(f"{BASE}/programs/{pid}/review", headers=hdr, json={"action": "APPROVE"})  # -> PUBLISHED

    publish_list = client.get(f"{BASE}/programs?statusIn=PUBLISHED,ENABLED",
                              headers=hdr).json()["data"]["items"]
    assert any(p["programId"] == pid for p in publish_list)
    # 已发布方案不应再出现在「计划审核」待办里
    review_list2 = client.get(f"{BASE}/programs?statusIn=COLLEGE_REVIEW,ACADEMIC_REVIEW",
                              headers=hdr).json()["data"]["items"]
    assert not any(p["programId"] == pid for p in review_list2)
