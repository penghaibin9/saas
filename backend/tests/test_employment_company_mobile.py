"""就业中心 · 移动端企业/岗位库（校级共享主数据，就业老师新增/停用）。

企业/岗位 CRUD 此前在 employment_service 已实现但无任何 router 暴露（孤儿能力），移动端
首次对外接入。门禁在 mobile.py 路由层用 employment.company/job.view/manage：EMPLOYMENT_TEACHER
走 employment.* 通配、SCHOOL_ADMIN 走 * 通配可写，其他教师身份(辅导员)无 employment.* → 403。
service 层已校验必填、停用原因≥5字、级联关闭岗位。
mock 账号：employment01=就业老师，counselor01=辅导员，school_admin01=校管。
"""
from __future__ import annotations

MOB = "/api/v1/mobile"


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def test_company_job_full_flow_via_mobile(client, db_mode):
    """就业老师新增企业→列表可见→在该企业下新增岗位→列表可见→停用企业级联关闭岗位。"""
    hdr = _hdr(client, "employment01")

    c = client.post(f"{MOB}/teacher/employment/companies", headers=hdr,
                    json={"name": "移动端合作企业", "creditCode": "MOBCC0000001", "industry": "软件", "city": "杭州"})
    assert c.status_code == 200 and c.json()["code"] == 0
    company_id = c.json()["data"]["id"]

    lst = client.get(f"{MOB}/teacher/employment/companies", headers=hdr).json()
    assert any(x["id"] == company_id and x["name"] == "移动端合作企业" for x in lst["data"]["list"])

    j = client.post(f"{MOB}/teacher/employment/jobs", headers=hdr,
                    json={"companyId": company_id, "title": "Java开发工程师", "salaryRange": "8-12K", "headcount": 3})
    assert j.status_code == 200 and j.json()["code"] == 0
    job_id = j.json()["data"]["id"]

    jobs = client.get(f"{MOB}/teacher/employment/jobs", headers=hdr,
                      params={"companyId": company_id}).json()["data"]["list"]
    assert any(x["id"] == job_id and x["title"] == "Java开发工程师" for x in jobs)

    # 停用企业 → 级联关闭其岗位（停用后该岗位不再 OPEN）
    dis = client.post(f"{MOB}/teacher/employment/companies/{company_id}/disable", headers=hdr,
                      json={"reason": "合作到期不再续约"})
    assert dis.status_code == 200
    jobs2 = client.get(f"{MOB}/teacher/employment/jobs", headers=hdr,
                       params={"companyId": company_id}).json()["data"]["list"]
    assert all(x["status"] != "OPEN" for x in jobs2 if x["id"] == job_id)


def test_company_required_fields_400_via_mobile(client, db_mode):
    """新增企业缺 name/creditCode → 400（service 层校验）。"""
    hdr = _hdr(client, "employment01")
    r = client.post(f"{MOB}/teacher/employment/companies", headers=hdr, json={"name": "只有名字"})
    assert r.status_code == 400


def test_disable_short_reason_400_via_mobile(client, db_mode):
    """停用企业原因 <5 字 → 400（service 层校验）。"""
    hdr = _hdr(client, "employment01")
    company_id = client.post(f"{MOB}/teacher/employment/companies", headers=hdr,
                             json={"name": "停用测试企业", "creditCode": "MOBCC0000002"}).json()["data"]["id"]
    r = client.post(f"{MOB}/teacher/employment/companies/{company_id}/disable", headers=hdr,
                    json={"reason": "太短"})
    assert r.status_code == 400


def test_job_disable_via_mobile(client, db_mode):
    """单独停用岗位（停用后不再 OPEN）。"""
    hdr = _hdr(client, "employment01")
    company_id = client.post(f"{MOB}/teacher/employment/companies", headers=hdr,
                             json={"name": "岗位测试企业", "creditCode": "MOBCC0000003"}).json()["data"]["id"]
    job_id = client.post(f"{MOB}/teacher/employment/jobs", headers=hdr,
                         json={"companyId": company_id, "title": "前端工程师"}).json()["data"]["id"]
    ok = client.post(f"{MOB}/teacher/employment/jobs/{job_id}/disable", headers=hdr,
                     json={"reason": "岗位已招满关闭"})
    assert ok.status_code == 200
    jobs = client.get(f"{MOB}/teacher/employment/jobs", headers=hdr,
                      params={"companyId": company_id}).json()["data"]["list"]
    assert all(x["status"] != "OPEN" for x in jobs if x["id"] == job_id)


def test_counselor_denied_company_write_via_mobile(client, db_mode):
    """辅导员(无 employment.* 权限)对企业库写操作 → 403（移动端路由门禁）。"""
    hdr = _hdr(client, "counselor01")
    r = client.post(f"{MOB}/teacher/employment/companies", headers=hdr,
                    json={"name": "辅导员越权企业", "creditCode": "MOBCCX90000"})
    assert r.status_code == 403


def test_counselor_denied_company_list_via_mobile(client, db_mode):
    """辅导员连企业列表(.view)也无权 → 403（企业库是就业老师专属工具）。"""
    hdr = _hdr(client, "counselor01")
    r = client.get(f"{MOB}/teacher/employment/companies", headers=hdr)
    assert r.status_code == 403


def test_school_admin_can_write_via_mobile(client, db_mode):
    """学校管理员(* 全权)可操作企业库。"""
    hdr = _hdr(client, "school_admin01")
    r = client.post(f"{MOB}/teacher/employment/companies", headers=hdr,
                    json={"name": "校管新增企业", "creditCode": "MOBCCADM0001"})
    assert r.status_code == 200 and r.json()["code"] == 0
