"""U14：风险数量在四处展示口径的一致性锁（总册 §41 补全）。

仓库里实际有四处会向老师展示"风险数量"，此前只核验过前两处：

1. `internship_risk_service.list_risks`（导出台账）
2. `internship_service.list_risk_students`（页面表格）
   —— 这两处是同一批风险单的两种投影，筛选条件必须逐项对齐，见
   `test_internship_v93_risk_count_cross_surface.py`。
3. `internship_service.get_dashboard_summary()`：工作台首页卡片「开放风险」+
   待办「开放风险待跟进」—— 口径是 **RiskRecord 行数**。
4. `internship_stats_service.overview()`：统计页 counters「风险学生数」—— 口径是
   **`distinct(internship_id)` 去重学生数**。

**3 和 4 的数字天然不相等，而且这是对的**：同一学生可以同时挂多张开放风险单
（系统预警升级单 + 学生自己提的求助单），"还有几条风险要处理"和"有几个学生处在
风险里"本来就是两个问题。真正的缺陷曾经在**标签**上——待办写的是"风险学生待跟进"
却在数风险单张数，老师看到 3 会以为有 3 个学生出事。

修复方式跟随看板卡片已有的处理（见 `test_internship_scope.py`
「看板卡片标签已从"风险学生"改为"开放风险"，口径不变」）：**保持口径、改正标签**。
不改成去重是因为该待办点开的就是逐条列风险单的处置页，数字必须与落地页行数对得上，
否则会制造一个更糟的不一致（待办说 2、点进去 3 行）。

本文件是该结论的回归锁：既锁住"两个数字确实不同"这一事实，也锁住"标签不得再暗示
它数的是学生人数"。
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

TID = 1000000000000000003


def _ctx(role="SCHOOL_ADMIN"):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": "1", "tenantId": str(TID), "realName": "探针",
               "userType": "ADMIN", "currentRoleCode": role, "activeContextId": "ctx"}
    set_current_user(payload)
    return payload


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed_two_open_risks_same_student(db):
    """一个批次 + 2 名学生：学生A 同时挂 2 张开放风险单（HIGH 升级单 + 求助单）；
    学生B 只挂 1 张开放风险单。合计 3 张开放风险单、2 名风险学生。"""
    from app.models import InternshipBatch, InternshipRecord, RiskRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="U14口径锁批次",
                            batch_no=f"U14-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()

    stu_a = StudentProfile(tenant_id=TID, student_no=f"U14A{uuid.uuid4().hex[:8]}",
                           real_name="风险学生A", grade="2024",
                           student_status="NORMAL", status="ACTIVE")
    stu_b = StudentProfile(tenant_id=TID, student_no=f"U14B{uuid.uuid4().hex[:8]}",
                           real_name="风险学生B", grade="2024",
                           student_status="NORMAL", status="ACTIVE")
    db.add_all([stu_a, stu_b])
    db.flush()

    rec_a = InternshipRecord(tenant_id=TID, student_id=stu_a.id, batch_id=batch.id,
                             status="ONBOARD", advisor_name="指导教师")
    rec_b = InternshipRecord(tenant_id=TID, student_id=stu_b.id, batch_id=batch.id,
                             status="ONBOARD", advisor_name="指导教师")
    db.add_all([rec_a, rec_b])
    db.flush()

    now = datetime.utcnow()
    # 学生A：2 张同时开放的风险单（同一学生、不同风险编码，业务上完全合法）
    db.add(RiskRecord(tenant_id=TID, internship_id=rec_a.id, risk_code="INT-R07",
                      risk_title="打卡异常", risk_level="HIGH", source_module="system",
                      status="PROCESSING", updated_at=now))
    db.add(RiskRecord(tenant_id=TID, internship_id=rec_a.id, risk_code="INT-R-HELP",
                      risk_title="学生求助", risk_level="MEDIUM", source_module="student_help",
                      status="PENDING_HANDLE", updated_at=now))
    # 学生B：1 张开放风险单
    db.add(RiskRecord(tenant_id=TID, internship_id=rec_b.id, risk_code="INT-R10",
                      risk_title="报告逾期", risk_level="MEDIUM", source_module="system",
                      status="PENDING_HANDLE", updated_at=now))
    db.flush()
    return batch.id


@pytest.fixture()
def seeded(db_mode):
    db = _session()
    batch_id = _seed_two_open_risks_same_student(db)
    db.commit()
    db.close()
    return batch_id


def _dashboard_and_stats(batch_id):
    user = _ctx()
    from app.modules.internship.services import internship_service as ix_svc
    from app.modules.internship.services import internship_stats_service as stats_svc

    dash = ix_svc.get_dashboard_summary(user=user, batch_id=str(batch_id))
    ov = stats_svc.overview(user, batch_id=str(batch_id))
    return dash, ov


def test_dashboard_counts_rows_and_stats_counts_students(seeded, db_mode):
    """两个数字确实不同，且各自都等于自己声称的东西：3 张风险单 / 2 名风险学生。"""
    dash, ov = _dashboard_and_stats(seeded)

    todo_risk = next((t for t in dash.get("todos", []) if t.get("id") == "todo-risk"), None)
    open_risk_card = next((c for c in dash.get("stats", []) if c.get("label") == "开放风险"), None)
    risk_students_counter = next(
        (c for c in ov.get("counters", []) if c.get("key") == "riskStudents"), None)

    assert todo_risk is not None, "工作台应给出开放风险待办"
    assert open_risk_card is not None, "工作台应给出「开放风险」卡片"
    assert risk_students_counter is not None, "统计页应给出「风险学生数」"

    assert todo_risk["count"] == 3, (
        f"待办口径应为风险单行数（3 张），实得 {todo_risk['count']}")
    assert str(open_risk_card["value"]) == "3", (
        f"「开放风险」卡片口径应为风险单行数（3 张），实得 {open_risk_card['value']}")
    assert risk_students_counter["value"] == 2, (
        f"「风险学生数」口径应为去重学生数（2 人），实得 {risk_students_counter['value']}")

    assert todo_risk["count"] != risk_students_counter["value"], (
        "这两个数字度量的是不同的东西（风险单张数 vs 风险学生人数），"
        "同一学生挂多张开放风险单时必然不等；若相等说明某一侧口径被改动，"
        "请同步复核本文件开头记录的结论。")


def test_dashboard_risk_labels_do_not_claim_student_headcount(seeded, db_mode):
    """回归锁：数风险单张数的两处，标签不得再出现「学生」，避免老师误读成学生人数。

    这正是本次修复的内容——待办原文案是「风险学生待跟进」却在数风险单张数。
    """
    dash, _ov = _dashboard_and_stats(seeded)

    todo_risk = next((t for t in dash.get("todos", []) if t.get("id") == "todo-risk"), None)
    open_risk_card = next((c for c in dash.get("stats", []) if c.get("label") == "开放风险"), None)

    assert "学生" not in todo_risk["label"], (
        f"待办 label「{todo_risk['label']}」在数风险单张数却写了「学生」，"
        "会被老师读成学生人数；要么改标签，要么把口径改成 distinct(internship_id)——"
        "但后者会与该待办点开的逐条风险单处置页行数对不上。")
    assert "学生" not in open_risk_card["label"], (
        f"卡片 label「{open_risk_card['label']}」在数风险单张数却写了「学生」。")


def test_stats_risk_students_label_matches_its_distinct_semantics(seeded, db_mode):
    """反向锁：真正按学生去重的那处，标签应当保留「学生」，不要被一起改掉。"""
    _dash, ov = _dashboard_and_stats(seeded)

    counter = next((c for c in ov.get("counters", []) if c.get("key") == "riskStudents"), None)
    assert "学生" in counter["label"], (
        f"「{counter['label']}」按 distinct(internship_id) 统计的就是学生人数，"
        "标签应保留「学生」字样。")
