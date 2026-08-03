"""毕业设计中心 · 导师管理 Batch 4 闭环测试：
导师评价（评分范围/等级/历史）+ 批量分配（容量/资格冲突跳过）+ 分配冲突自动检测 + 批量归档。
全部经 HTTP client 走真库(db_mode)。"""
from __future__ import annotations

from conftest import make_org_class

STU = "/api/v1/students"
GD_STU = "/api/v1/graduation/gd-students"
M = "/api/v1/graduation/gd-mentors"


def _mentor(graduation_client, h, no, name, capacity=8, qualify=True):
    mid = graduation_client.post(M, headers=h, json={"teacherNo": no, "teacherName": name, "maxCapacity": capacity}).json()["data"]["id"]
    if qualify:
        graduation_client.post(f"{M}/{mid}/review", headers=h, json={"action": "APPROVE"})
    return mid


def _gd_student(graduation_client, h, no, name):
    sid = graduation_client.post(STU, headers=h, json={"studentNo": no, "realName": name, "classId": make_org_class()}).json()["data"]["id"]
    return graduation_client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def test_mentor_eval_range_level_and_history(graduation_client, auth_headers, db_mode):
    h = auth_headers
    mid = _mentor(graduation_client, h, "EV1", "评价导师")

    bad_score = graduation_client.post(f"{M}/{mid}/evals", headers=h, json={"score": 120, "level": "优秀"})
    assert bad_score.json()["code"] != 0
    bad_level = graduation_client.post(f"{M}/{mid}/evals", headers=h, json={"score": 90, "level": "满分"})
    assert bad_level.json()["code"] != 0

    ok = graduation_client.post(f"{M}/{mid}/evals", headers=h, json={"score": 92, "level": "优秀", "note": "指导认真", "period": "2026春"})
    assert ok.json()["code"] == 0
    graduation_client.post(f"{M}/{mid}/evals", headers=h, json={"score": 80, "level": "良好"})

    hist = graduation_client.get(f"{M}/{mid}/evals", headers=h).json()["data"]["items"]
    assert len(hist) == 2

    detail = graduation_client.get(f"{M}/{mid}", headers=h).json()["data"]
    assert detail["latestEval"]["level"] == "良好"  # 最新一条


def test_batch_assign_skips_capacity_and_unqualified(graduation_client, auth_headers, db_mode):
    h = auth_headers
    m_full = _mentor(graduation_client, h, "BA1", "满员导师", capacity=1)
    m_ok = _mentor(graduation_client, h, "BA2", "可用导师", capacity=5)
    m_bad = _mentor(graduation_client, h, "BA3", "未认证导师", qualify=False)
    g1 = _gd_student(graduation_client, h, "BS1", "批量甲")
    g2 = _gd_student(graduation_client, h, "BS2", "批量乙")
    g3 = _gd_student(graduation_client, h, "BS3", "批量丙")

    body = {"assignments": [
        {"gdStudentId": g1, "mentorId": m_full},   # ok（占满 capacity=1）
        {"gdStudentId": g2, "mentorId": m_full},   # skip：满员
        {"gdStudentId": g3, "mentorId": m_bad},    # skip：未认证
    ]}
    res = graduation_client.post(f"{M}/batch-assign", headers=h, json=body).json()["data"]
    assert res["assigned"] == 1 and res["skipped"] == 2

    # 补分配 g2 给可用导师成功
    res2 = graduation_client.post(f"{M}/batch-assign", headers=h, json={"assignments": [{"gdStudentId": g2, "mentorId": m_ok}]}).json()["data"]
    assert res2["assigned"] == 1


def test_conflicts_and_batch_archive(graduation_client, auth_headers, db_mode):
    h = auth_headers
    # 未认证导师 + 停用导师（可批量归档）
    m_bad = _mentor(graduation_client, h, "CF1", "待归档导师", qualify=True)
    graduation_client.post(f"{M}/{m_bad}/disable", headers=h, json={"reason": "本届不再带教"})

    conflicts = graduation_client.get(f"{M}/conflicts", headers=h).json()["data"]
    assert "overCapacity" in conflicts and "advancedNoMentor" in conflicts and "total" in conflicts

    res = graduation_client.post(f"{M}/batch-archive", headers=h, json={"mentorIds": [m_bad]}).json()["data"]
    assert res["archived"] == 1

    after = graduation_client.get(f"{M}/{m_bad}", headers=h).json()["data"]
    assert after["qualificationStatus"] == "ARCHIVED"
