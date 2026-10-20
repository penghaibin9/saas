"""U14：风险台账「页面列表」与「导出」筛选口径必须逐项一致。

老师在风险处置页用「风险聚焦」标签（未落岗 / 打卡异常 / 报告逾期 / 请假未返岗 /
超期未归 / 离岗异常）筛完之后点导出，页面和导出走的是**两个不同的服务函数**：

- 页面表格：`internship_service.list_risk_students`（支持 level/status/keyword/risk_code）
- 导出台账：`internship_risk_service.export_risks → list_risks`

修复前 `list_risks` 根本没有 `risk_code` 参数，路由 `POST /risks/export` 也没声明
`riskCode`——FastAPI 对未声明的查询参数静默丢弃，于是老师在「打卡异常」标签下看到
1 条、导出拿到整批 3 条，且没有任何提示。成绩/风险这类要报出去的东西，"多给了"
比"慢"危险得多。

本文件把"两个投影的筛选口径一致"变成可执行断言：对每一种筛选组合，两条路径必须
选出**完全相同的风险单 id 集合**。行的字段投影不同（导出多了指导教师、企业等列）
是设计使然，因此只比对 id 集合与总数，不比对字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

TID = 1000000000000000005


def _ctx(role="SCHOOL_ADMIN"):
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": "1", "tenantId": str(TID), "realName": "实习处",
               "userType": "ADMIN", "currentRoleCode": role, "activeContextId": "ctx"}
    set_current_user(payload)
    return payload


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db):
    """3 名学生 × 覆盖多种 risk_code / level / status 的风险单，
    确保每一种筛选组合都能选出「非空且非全集」的子集——否则断言相等没有意义。"""
    from app.models import InternshipBatch, InternshipRecord, RiskRecord, StudentProfile

    batch = InternshipBatch(tenant_id=TID, batch_name="U14跨端口径批次",
                            batch_no=f"U14X-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()

    records = []
    for i, name in enumerate(["张三风", "李四险", "王五单"]):
        stu = StudentProfile(tenant_id=TID, student_no=f"U14X{i}{uuid.uuid4().hex[:6]}",
                             real_name=name, grade="2024",
                             student_status="NORMAL", status="ACTIVE")
        db.add(stu)
        db.flush()
        rec = InternshipRecord(tenant_id=TID, student_id=stu.id, batch_id=batch.id,
                               status="ONBOARD", advisor_name="指导教师",
                               enterprise_name="测试企业")
        db.add(rec)
        db.flush()
        records.append((rec, stu))

    now = datetime.utcnow()
    # (记录下标, risk_code, level, status)
    plan = [
        (0, "INT-R07", "HIGH", "PROCESSING"),
        (0, "INT-R10", "MEDIUM", "PENDING_HANDLE"),
        (1, "INT-R07", "MEDIUM", "PENDING_HANDLE"),
        (1, "INT-R06", "LOW", "CLOSED"),
        (2, "INT-R02", "HIGH", "PENDING_HANDLE"),
        (2, "INT-R07", "LOW", "CLOSED"),
    ]
    for idx, code, level, status in plan:
        rec, _stu = records[idx]
        db.add(RiskRecord(tenant_id=TID, internship_id=rec.id, risk_code=code,
                          risk_title=f"{code}风险", risk_level=level,
                          source_module="system", status=status, updated_at=now))
    db.flush()
    return batch.id, [(rec.id, stu.real_name, stu.student_no) for rec, stu in records]


@pytest.fixture()
def seeded(db_mode):
    db = _session()
    batch_id, students = _seed(db)
    db.commit()
    db.close()
    return batch_id, students


# 覆盖：无筛选 / 每种「风险聚焦」标签 / 等级 / 状态 / 组合筛选
FILTER_CASES = [
    {},
    {"risk_code": "INT-R07"},
    {"risk_code": "INT-R10"},
    {"risk_code": "INT-R06"},
    {"risk_code": "INT-R02"},
    {"risk_code": "INT-R99-不存在"},
    {"level": "HIGH"},
    {"level": "MEDIUM"},
    {"level": "LOW"},
    {"status": "PENDING_HANDLE"},
    {"status": "PROCESSING"},
    {"status": "CLOSED"},
    {"risk_code": "INT-R07", "status": "PENDING_HANDLE"},
    {"risk_code": "INT-R07", "level": "HIGH"},
    {"risk_code": "INT-R06", "status": "PROCESSING"},
    {"level": "HIGH", "status": "CLOSED"},
]


@pytest.mark.parametrize("filters", FILTER_CASES,
                         ids=[str(sorted(f.items())) for f in FILTER_CASES])
def test_page_list_and_export_select_identical_rows(seeded, db_mode, filters):
    """每种筛选组合下，页面表格与导出必须选出同一批风险单 id。"""
    batch_id, _students = seeded
    user = _ctx()
    from app.modules.internship.services import internship_risk_service as risk_svc
    from app.modules.internship.services import internship_service as ix_svc

    page_items, page_total = ix_svc.list_risk_students(
        1, 1000, user=user, batch_id=str(batch_id), **filters)
    export_items, export_total = risk_svc.list_risks(
        1, 1000, user=user, batch_id=str(batch_id), **filters)

    page_ids = sorted(int(it["id"]) for it in page_items)
    export_ids = sorted(int(it["id"]) for it in export_items)

    assert page_ids == export_ids, (
        f"筛选 {filters} 下页面与导出选出的风险单不一致：\n"
        f"页面={page_ids}\n导出={export_ids}\n"
        "老师会「页面看到 N 条、导出拿到 M 条」。")
    assert page_total == export_total, (
        f"筛选 {filters} 下 total 不一致：页面={page_total} 导出={export_total}")


def test_riskcode_filter_actually_narrows(seeded, db_mode):
    """反证：如果 risk_code 根本没生效，上面的相等断言会因「两边都是全集」而假绿。"""
    batch_id, _students = seeded
    user = _ctx()
    from app.modules.internship.services import internship_risk_service as risk_svc

    all_items, all_total = risk_svc.list_risks(1, 1000, user=user, batch_id=str(batch_id))
    r07_items, r07_total = risk_svc.list_risks(
        1, 1000, user=user, batch_id=str(batch_id), risk_code="INT-R07")

    assert all_total == 6, f"种子应有 6 张风险单，实得 {all_total}"
    assert r07_total == 3, f"INT-R07 应命中 3 张，实得 {r07_total}——risk_code 没有真正生效"
    assert r07_total < all_total, "risk_code 筛选没有收窄结果集，断言相等就是假绿"
    assert all(it["riskCode"] == "INT-R07" for it in r07_items), "筛出了非 INT-R07 的风险单"


def test_keyword_matches_student_no_on_both_surfaces(seeded, db_mode):
    """keyword 口径对齐：页面按 姓名或学号 匹配，导出此前只匹配姓名，用学号搜会导出 0 条。"""
    batch_id, students = seeded
    user = _ctx()
    from app.modules.internship.services import internship_risk_service as risk_svc
    from app.modules.internship.services import internship_service as ix_svc

    _rec_id, real_name, student_no = students[0]

    for kw, what in [(student_no, "学号"), (real_name, "姓名")]:
        page_items, _ = ix_svc.list_risk_students(
            1, 1000, user=user, batch_id=str(batch_id), keyword=kw)
        export_items, _ = risk_svc.list_risks(
            1, 1000, user=user, batch_id=str(batch_id), keyword=kw)
        page_ids = sorted(int(it["id"]) for it in page_items)
        export_ids = sorted(int(it["id"]) for it in export_items)
        assert page_ids, f"按{what}「{kw}」搜索应能命中该学生的风险单，种子无效"
        assert page_ids == export_ids, (
            f"按{what}「{kw}」搜索时页面与导出不一致：页面={page_ids} 导出={export_ids}")


def test_export_packs_the_filtered_rows_not_the_whole_batch(seeded, db_mode):
    """端到端：export_risks() 真正打包的行数必须等于筛选后的条数，而不是整批。

    这是 U14 缺陷的最终形态——前端把 riskCode 传给了导出接口，但它被丢弃，
    老师拿到的 xlsx 比页面多。
    """
    batch_id, _students = seeded
    user = _ctx()
    from app.modules.internship.services import internship_risk_service as risk_svc
    from app.modules.internship.services import internship_service as ix_svc

    page_items, page_total = ix_svc.list_risk_students(
        1, 1000, user=user, batch_id=str(batch_id), risk_code="INT-R07")
    packed = risk_svc.export_risks(user=user, batch_id=str(batch_id), risk_code="INT-R07")

    assert page_total == 3
    assert packed["rowCount"] == page_total == len(page_items), (
        f"导出打包 {packed['rowCount']} 行，页面显示 {page_total} 条——导出没有接住 riskCode")
