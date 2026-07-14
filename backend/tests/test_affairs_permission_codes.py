"""学工中心 · 细分权限码 seed 专项测试（真实 MySQL）。

覆盖本轮回写 §12 的新细分权限码是否落到正确角色：
- 单元层：has_permission() 角色×权限码矩阵（授权命中 / 越权拒绝 / SCHOOL_ADMIN 仍通配）。
- 端点层：funding.workstudy / discipline.appeal.review / counselorEval.manage 三代表端点正反用例
  （非授权角色 403 NO_PERMISSION 越权门禁；授权角色放行——可写端点真 200，只读复核端点非 NO_PERMISSION）。

新增角色：FUNDING_TEACHER（资助老师）/ YOUTH_LEAGUE（团委）/ ORG_PERSONNEL（组织人事）。
SCHOOL_ADMIN 仍 {"*"} 通配不受影响。
"""
from __future__ import annotations

from app.core.permissions import has_permission

BASE = "/api/v1/student-affairs"


def _u(role: str) -> dict:
    return {"currentRoleCode": role, "userType": "TEACHER", "userId": "u_test"}


def _hdr(client, login):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


# ════════════ 一、单元层：角色 × 新权限码矩阵 ════════════

def test_funding_teacher_capabilities():
    ft = _u("FUNDING_TEACHER")
    for code in ("studentAffairs.funding.workstudy.manage", "studentAffairs.funding.loan.manage",
                 "studentAffairs.funding.reduction.manage", "studentAffairs.funding.disburse.manage",
                 "studentAffairs.funding.publicity.manage", "studentAffairs.aid.approve"):
        assert has_permission(ft, code), f"资助老师应拥有 {code}"
    # 资助老师不得越域拿到违纪/考评/社团
    for code in ("studentAffairs.discipline.deliver", "studentAffairs.discipline.appeal.review",
                 "studentAffairs.counselorEval.manage", "studentAffairs.club.manage",
                 "studentAffairs.league.manage"):
        assert not has_permission(ft, code), f"资助老师不应拥有 {code}"


def test_youth_league_capabilities():
    yl = _u("YOUTH_LEAGUE")
    for code in ("studentAffairs.club.view", "studentAffairs.club.manage", "studentAffairs.org.manage",
                 "studentAffairs.league.manage", "studentAffairs.activity.create"):
        assert has_permission(yl, code), f"团委应拥有 {code}"
    for code in ("studentAffairs.funding.workstudy.manage", "studentAffairs.counselorEval.manage",
                 "studentAffairs.discipline.deliver"):
        assert not has_permission(yl, code), f"团委不应拥有 {code}"


def test_org_personnel_capabilities():
    op = _u("ORG_PERSONNEL")
    assert has_permission(op, "studentAffairs.counselorEval.view")
    assert has_permission(op, "studentAffairs.counselorEval.manage")
    for code in ("studentAffairs.funding.workstudy.manage", "studentAffairs.club.manage",
                 "studentAffairs.aid.approve", "studentAffairs.discipline.deliver"):
        assert not has_permission(op, code), f"组织人事不应拥有 {code}"


def test_counselor_self_service_eval_only():
    """辅导员对本人考评仅有 view + appeal.create，绝无 manage（考评/复核）。"""
    c = _u("COUNSELOR")
    assert has_permission(c, "studentAffairs.counselorEval.view")
    assert has_permission(c, "studentAffairs.counselorEval.appeal.create")
    assert not has_permission(c, "studentAffairs.counselorEval.manage")
    assert not has_permission(c, "studentAffairs.funding.workstudy.manage")
    assert not has_permission(c, "studentAffairs.discipline.appeal.review")


def test_school_admin_wildcard_unaffected():
    """SCHOOL_ADMIN 仍通配：任意新码均命中。"""
    sa = {"currentRoleCode": "SCHOOL_ADMIN", "userType": "ADMIN", "userId": "u"}
    for code in ("studentAffairs.funding.workstudy.manage", "studentAffairs.discipline.appeal.review",
                 "studentAffairs.counselorEval.manage", "studentAffairs.club.manage"):
        assert has_permission(sa, code)


def test_student_affairs_admin_prefix_covers_new_codes():
    """学工处管理员 studentAffairs.* 前缀通配覆盖全部新码（不因新增 seed 而漏授）。"""
    sa = _u("STUDENT_AFFAIRS_ADMIN")
    for code in ("studentAffairs.funding.workstudy.manage", "studentAffairs.discipline.appeal.review",
                 "studentAffairs.counselorEval.manage", "studentAffairs.league.manage"):
        assert has_permission(sa, code)


# ════════════ 二、端点层：funding.workstudy.manage 正反 ════════════

def test_workstudy_manage_denied(client, db_mode):
    """越权门禁：辅导员/宿管无 workstudy.manage → 403 NO_PERMISSION。"""
    for login in ("counselor01", "dorm01"):
        r = client.post(f"{BASE}/work-study/posts", headers=_hdr(client, login),
                        json={"deptName": "图书馆", "postName": "整理员"})
        assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION", login


def test_workstudy_manage_allowed(client, db_mode):
    """授权角色：资助老师发布勤工岗位 → 200。"""
    r = client.post(f"{BASE}/work-study/posts", headers=_hdr(client, "funding01"),
                    json={"deptName": "图书馆", "postName": "整理员", "headcount": 2})
    assert r.status_code == 200 and r.json()["code"] == 0, r.text


# ════════════ 三、端点层：counselorEval.manage 正反 ════════════

def test_counselor_eval_manage_denied(client, db_mode):
    """越权门禁：辅导员仅有 counselorEval.view，无 manage → 建指标 403。"""
    r = client.post(f"{BASE}/counselor-eval/indicators", headers=_hdr(client, "counselor01"),
                    json={"name": "师德师风"})
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"


def test_counselor_eval_manage_allowed(client, db_mode):
    """授权角色：组织人事建考评指标 → 200。"""
    r = client.post(f"{BASE}/counselor-eval/indicators", headers=_hdr(client, "orgperson01"),
                    json={"name": "师德师风", "weight": 30, "maxScore": 100})
    assert r.status_code == 200 and r.json()["code"] == 0, r.text


# ════════════ 四、端点层：discipline.appeal.review 正反 ════════════

def test_discipline_appeal_review_denied(client, db_mode):
    """越权门禁：辅导员无 discipline.appeal.review → 复核 403。"""
    r = client.post(f"{BASE}/discipline/appeals/999999/review", headers=_hdr(client, "counselor01"),
                    json={"result": "UPHELD", "opinion": "维持原处分决定"})
    assert r.status_code == 403 and r.json()["bizCode"] == "NO_PERMISSION"


def test_discipline_appeal_review_permission_passes(client, db_mode):
    """授权角色：学工处管理员通过能力门禁（申诉不存在→业务错，绝非 NO_PERMISSION）。"""
    r = client.post(f"{BASE}/discipline/appeals/999999/review", headers=_hdr(client, "sa_admin01"),
                    json={"result": "UPHELD", "opinion": "维持原处分决定"})
    body = r.json()
    assert not (r.status_code == 403 and body.get("bizCode") == "NO_PERMISSION"), body
