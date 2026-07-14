"""13A 增强(a) · 二课积分类目加权成绩单（真实 MySQL）。

类目系数 t_affairs_credit_category.weight 对类目原始合计加权（byCategoryWeighted + weightedTotal）；
原始明细/byCategory 原始合计不变，不回改历史 credit 行。缺省系数=1（加权=原始）。
"""
from __future__ import annotations

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivityCredit, StudentProfile
    db = get_sessionmaker()()
    try:
        s = StudentProfile(tenant_id=TID, student_no="W0001", real_name="加权生", gender="男",
                           current_stage="STUDYING", student_status="NORMAL", status="ACTIVE")
        db.add(s); db.flush()
        # SC1 原始合计 10（5+5，两活动），SC2 原始合计 8
        rows = [
            AffairsActivityCredit(tenant_id=TID, student_id=s.id, activity_id=9001,
                                  credit_type="SECOND_CLASS", credit_value=5, category_code="WSC1"),
            AffairsActivityCredit(tenant_id=TID, student_id=s.id, activity_id=9002,
                                  credit_type="SECOND_CLASS", credit_value=5, category_code="WSC1"),
            AffairsActivityCredit(tenant_id=TID, student_id=s.id, activity_id=9003,
                                  credit_type="SECOND_CLASS", credit_value=8, category_code="WSC2"),
        ]
        db.add_all(rows); db.commit()
        return s.id
    finally:
        db.close()


def test_credit_weighted_report(client, db_mode):
    sid = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 配类目系数：WSC1×2、WSC2×0.5
    client.post(f"{BASE}/second-class/categories", headers=hdr,
                json={"categoryCode": "WSC1", "categoryName": "创新创业W", "weight": 2})
    client.post(f"{BASE}/second-class/categories", headers=hdr,
                json={"categoryCode": "WSC2", "categoryName": "文体活动W", "weight": 0.5})
    rep = client.get(f"{BASE}/second-class/students/{sid}/report", headers=hdr).json()["data"]
    # 原始合计不变
    assert rep["rawTotal"] == 18.0, rep
    raw = {x["key"]: x["value"] for x in rep["byCategory"]}
    assert raw["WSC1"] == 10.0 and raw["WSC2"] == 8.0
    # 加权：WSC1 10×2=20，WSC2 8×0.5=4 → 24
    wt = {x["key"]: x["value"] for x in rep["byCategoryWeighted"]}
    assert wt["WSC1"] == 20.0 and wt["WSC2"] == 4.0
    assert rep["weightedTotal"] == 24.0, rep


def test_category_default_weight_is_one(client, db_mode):
    """不传 weight 建类目→系数默认 1，加权=原始。"""
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{BASE}/second-class/categories", headers=hdr,
                    json={"categoryCode": "WDEF", "categoryName": "默认系数"}).json()
    assert r["code"] == 0 and float(r["data"]["weight"]) == 1.0
    cats = {c["categoryCode"]: c for c in
            client.get(f"{BASE}/second-class/categories", headers=hdr).json()["data"]["items"]}
    assert float(cats["WDEF"]["weight"]) == 1.0
