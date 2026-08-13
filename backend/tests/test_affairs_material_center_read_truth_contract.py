"""V5-C2/C3 材料中心读侧真实性合同（真实 DB 模式）。

锁住两个"页面结果与数据库真实结果不同"的缺陷：

C2 敏感级别先分页再过滤：material_overview 先按 status 取一页，再在 Python 里筛
   sensitivityLevel 并把 total 改成当前页命中数。强敏感材料落在第 2 页时，页面
   会告诉老师"0 条"，而库里真实存在。

C3 summary 按当前页统计：total 是授权范围真值，missing/pendingReview/accepted/
   highlySensitive 却是当前页 items 的计数，两个口径混在同一排概览卡片里。

要求：两者都改为与列表同 scope、同 filter 的 SQL 条件过滤与聚合，
且不得把全量对象 materialize 到 Python。
"""
from __future__ import annotations

TID = 1000000000000000001

PAGE_SIZE = 50
# 总册要求用 160+ 条材料验证跨页真值。后建的 120 条普通材料会占满前两页，
# 先建的 40 条强敏感材料因此只会出现在第 3 页及以后。
PLAIN_COUNT = 120
SENSITIVE_COUNT = 40
TOTAL_COUNT = PLAIN_COUNT + SENSITIVE_COUNT


# 登录接口有限流（每 IP 每分钟 10 次）。同一登录名在本文件内复用令牌，
# 否则多个用例合并跑时会撞上 RATE_LIMITED，表现为 data=None 的 TypeError。
_TOKENS: dict[str, str] = {}


def _hdr(client, login_name):
    token = _TOKENS.get(login_name)
    if not token:
        body = client.post("/api/v1/auth/mock-login",
                           json={"loginName": login_name, "password": "any"}).json()
        assert body.get("code") == 0, f"登录失败：{body}"
        token = body["data"]["accessToken"]
        _TOKENS[login_name] = token
    return {"Authorization": f"Bearer {token}"}


def _seed(db_mode):
    """全部落在同一个授权业务域(DISCIPLINE)，只让敏感级别和状态成为变量。

    用 school_admin01（mock 演示账号，TENANT_ALL）避免数据范围成为干扰变量：
    本合同要验证的是"筛选/计数是否在 SQL 里发生"，范围裁剪由既有用例覆盖。

    敏感材料的 requirement 先建（id 小）→ 倒序排在后面 → 必然落到第 2 页之后。
    """
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile
    from app.models.affairs_operations import AffairsMaterialRequirement

    db = get_sessionmaker()()

    college = College(tenant_id=TID, college_name="C2材料学院",
                      code="C2-COLLEGE", status="ACTIVE")
    db.add(college)
    db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="C2材料专业",
                  code="C2-MAJOR", status="ACTIVE")
    db.add(major)
    db.flush()
    klass = SchoolClass(tenant_id=TID, major_id=major.id, class_name="C2班",
                        grade="2024", status="ACTIVE")
    db.add(klass)
    db.flush()

    student = StudentProfile(tenant_id=TID, student_no="C2STU0001", real_name="材料测试学生",
                             class_id=klass.id, college_id=college.id, gender="M",
                             current_stage="CAMPUS", student_status="NORMAL", status="ACTIVE")
    db.add(student)
    db.flush()

    def add_req(idx, sensitivity, status):
        db.add(AffairsMaterialRequirement(
            tenant_id=TID, student_id=student.id, biz_type="DISCIPLINE", biz_id=10000 + idx,
            item_code=f"C2ITEM{idx:04d}", item_name=f"材料项{idx:04d}",
            requirement_reason="读侧真实性合同用例", status=status,
            sensitivity_level=sensitivity, material_scope="BUSINESS_SCOPE",
        ))

    # ① 先建强敏感（id 小 → 倒序在后 → 落到第 2 页之后）
    for i in range(SENSITIVE_COUNT):
        add_req(i, "HIGHLY_SENSITIVE", "PENDING_REVIEW" if i % 2 else "MISSING")
    # ② 再建普通材料，占满第 1 页
    for i in range(SENSITIVE_COUNT, TOTAL_COUNT):
        add_req(i, "SENSITIVE", "ACCEPTED" if i % 2 else "MISSING")

    db.commit()
    ids = {"student": student.id, "class": klass.id}
    db.close()
    return ids


def _center(client, hdr, **params):
    response = client.get("/api/v1/student-affairs/material-center",
                          headers=hdr, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def _expected_counts():
    """按 _seed 的构造直接算出真值，避免用被测代码自证。"""
    missing = sum(1 for i in range(SENSITIVE_COUNT) if i % 2 == 0)          # 强敏感 MISSING
    missing += sum(1 for i in range(SENSITIVE_COUNT, TOTAL_COUNT) if i % 2 == 0)
    pending = sum(1 for i in range(SENSITIVE_COUNT) if i % 2)
    accepted = sum(1 for i in range(SENSITIVE_COUNT, TOTAL_COUNT) if i % 2)
    return {"missing": missing, "pendingReview": pending, "accepted": accepted,
            "highlySensitive": SENSITIVE_COUNT}


def test_sensitive_materials_are_absent_from_first_page(client, db_mode):
    """前置事实：强敏感材料确实不在第 1 页（否则本合同测不到跨页问题）。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    page1 = _center(client, hdr, page=1, pageSize=PAGE_SIZE)
    levels = {item["sensitivityLevel"] for item in page1["items"]}
    assert "HIGHLY_SENSITIVE" not in levels, "测试数据构造失效：第 1 页不应有强敏感材料"
    assert page1["total"] == TOTAL_COUNT, page1["total"]


def test_sensitivity_filter_finds_records_beyond_first_page(client, db_mode):
    """C2 核心：敏感级别必须在 SQL 分页前过滤，跨页的强敏感材料必须能被筛出来。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")

    filtered = _center(client, hdr, page=1, pageSize=PAGE_SIZE,
                       sensitivityLevel="HIGHLY_SENSITIVE")
    assert filtered["total"] == SENSITIVE_COUNT, (
        f"强敏感真实总数应为 {SENSITIVE_COUNT}，得到 {filtered['total']}"
        "（先分页再 Python 过滤会得到 0）"
    )
    assert len(filtered["items"]) == min(PAGE_SIZE, SENSITIVE_COUNT)
    assert {item["sensitivityLevel"] for item in filtered["items"]} == {"HIGHLY_SENSITIVE"}


def test_sensitivity_filter_paging_has_no_gap_or_duplicate(client, db_mode):
    """筛选条件下的分页必须真实：逐页累计等于 total，且无重复。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")

    seen, page = [], 1
    while True:
        data = _center(client, hdr, page=page, pageSize=15,
                       sensitivityLevel="HIGHLY_SENSITIVE")
        assert data["total"] == SENSITIVE_COUNT, data["total"]
        seen.extend(str(item["requirementId"]) for item in data["items"])
        if not data["items"] or len(seen) >= data["total"]:
            break
        page += 1
    assert len(seen) == SENSITIVE_COUNT, f"逐页累计 {len(seen)} != {SENSITIVE_COUNT}"
    assert len(set(seen)) == SENSITIVE_COUNT, "分页出现重复记录"


def test_summary_counts_whole_scope_not_current_page(client, db_mode):
    """C3 核心：summary 必须是授权范围全量聚合，不能是当前页 items 的统计。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    expected = _expected_counts()

    # 用很小的 pageSize：page-local 统计会明显小于真值。
    small = _center(client, hdr, page=1, pageSize=5)
    assert small["summary"]["total"] == TOTAL_COUNT, small["summary"]
    assert small["summary"]["highlySensitive"] == expected["highlySensitive"], (
        f"强敏感应为 {expected['highlySensitive']}，得到 "
        f"{small['summary']['highlySensitive']}（当前页统计只会得到 0）"
    )
    assert small["summary"]["missing"] == expected["missing"], small["summary"]
    assert small["summary"]["pendingReview"] == expected["pendingReview"], small["summary"]
    assert small["summary"]["accepted"] == expected["accepted"], small["summary"]

    # 换页不改变概览口径。
    page2 = _center(client, hdr, page=2, pageSize=5)
    assert page2["summary"] == small["summary"], "翻页不应改变全量概览数字"


def test_summary_follows_the_same_filters_as_the_list(client, db_mode):
    """加了筛选后，summary 必须是"筛选后的全量"，与 total 同口径。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")

    data = _center(client, hdr, page=1, pageSize=5, sensitivityLevel="HIGHLY_SENSITIVE")
    assert data["total"] == SENSITIVE_COUNT
    assert data["summary"]["total"] == SENSITIVE_COUNT
    assert data["summary"]["highlySensitive"] == SENSITIVE_COUNT
    assert data["summary"]["accepted"] == 0, "强敏感集合里没有 ACCEPTED，概览不应算进来"

    by_status = _center(client, hdr, page=1, pageSize=5, status="MISSING")
    expected_missing = _expected_counts()["missing"]
    assert by_status["total"] == expected_missing, by_status["total"]
    assert by_status["summary"]["missing"] == expected_missing
    assert by_status["summary"]["pendingReview"] == 0
    assert by_status["summary"]["accepted"] == 0


def test_unknown_sensitivity_returns_empty_not_full_scope(client, db_mode):
    """非法/不存在的敏感级别必须返回空，绝不能回落成"返回全部"。"""
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    data = _center(client, hdr, page=1, pageSize=PAGE_SIZE, sensitivityLevel="NO_SUCH_LEVEL")
    assert data["total"] == 0, data["total"]
    assert data["items"] == []
    assert data["summary"]["total"] == 0
