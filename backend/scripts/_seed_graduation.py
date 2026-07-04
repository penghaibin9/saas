"""毕业设计域种子（主租户；幂等）。独立台账。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import (GraduationAuditTrail, GraduationDefenseGroup, GraduationFinal,
                        GraduationProposal, GraduationStudent, GraduationTopic)

TID = 1000000000000000001


def seed_graduation(db, tenant_id: int = TID) -> dict:
    if db.scalars(select(GraduationStudent).where(GraduationStudent.tenant_id == tenant_id)).first():
        return {"skipped": True}
    now = datetime.now()
    advisors = ["王芳", "钱立群", "孙晓梅"]
    classes = [("c-2301", "软件2301"), ("c-2302", "软件2302")]
    stages = ["TOPIC_SELECTING", "GUIDING", "MIDTERM", "FINAL_CHECK", "FINAL_CHECK", "DEFENSE",
              "GUIDING", "FINAL_CHECK", "MIDTERM", "TOPIC_SELECTING"]
    stus = []
    for i in range(10):
        cid, cname = classes[i % 2]
        risk = ["NONE", "LOW", "NONE", "MEDIUM", "NONE", "NONE", "HIGH", "LOW", "NONE", "MEDIUM"][i]
        s = GraduationStudent(tenant_id=tenant_id, name=f"毕设生{i + 1:02d}", student_no=f"S2026-{i + 1:06d}",
                              student_id=None, class_id=cid, class_name=cname,
                              topic_title=f"基于 Vue3 的课题{i + 1} 设计与实现" if i not in (0, 9) else None,
                              topic_source="教师申报", advisor_name=advisors[i % 3], stage=stages[i],
                              material_summary="定稿 v3 待审" if stages[i] == "FINAL_CHECK" else "指导中",
                              plagiarism_rate="12.6%" if stages[i] in ("FINAL_CHECK", "DEFENSE") else None,
                              risk_level=risk, phone_encrypted=f"136{12340000 + i:08d}",
                              midterm_conclusion="通过" if stages[i] in ("FINAL_CHECK", "DEFENSE") else None,
                              defense_group="第 3 组" if stages[i] == "DEFENSE" else None)
        db.add(s)
        db.flush()
        stus.append(s)

    # 选题 5 条
    for i in range(5):
        db.add(GraduationTopic(tenant_id=tenant_id, title=f"课题库-{i + 1}：智慧校园子系统设计",
                               source="教师申报" if i % 2 == 0 else "企业课题", advisor_name=advisors[i % 3],
                               major_name="软件技术", capacity=2, selected=1 if i < 3 else 0,
                               status="CONFIRMED" if i < 3 else "PENDING_CONFIRM",
                               students_json=[f"毕设生{i + 1:02d}"] if i < 3 else []))

    # 开题材料：待审 3 条 + 通过 1 + 驳回 1
    for idx, (sid_idx, st, ver, resub) in enumerate([
        (1, "PENDING_REVIEW", "v1", False), (6, "PENDING_REVIEW", "v2", True),
        (8, "PENDING_REVIEW", "v1", False), (2, "APPROVED", "v1", False),
        (3, "REJECTED", "v1", False)]):
        db.add(GraduationProposal(tenant_id=tenant_id, gd_student_id=stus[sid_idx].id, version=ver,
                                  is_resubmit=resub, submit_at=now - timedelta(days=idx + 1),
                                  background="针对校园场景的痛点开展研究。", plan="分三阶段推进：调研、开发、测试。",
                                  outcome="交付可运行系统与论文。", attachments_json=["开题报告.docx", "文献综述.pdf"],
                                  status=st, reviewer=advisors[sid_idx % 3] if st != "PENDING_REVIEW" else None,
                                  review_comment="内容需补充进度计划" if st == "REJECTED" else None))

    # 成果提交：待审 2 + 通过 1（含查重）
    for idx, (sid_idx, st, ftype, ver, rate, pstat) in enumerate([
        (3, "PENDING_REVIEW", "定稿", "v3", "12.6%", "达标"),
        (4, "PENDING_REVIEW", "定稿", "v2", "18.4%", "达标"),
        (5, "APPROVED", "定稿", "v3", "9.2%", "达标")]):
        db.add(GraduationFinal(tenant_id=tenant_id, gd_student_id=stus[sid_idx].id, final_type=ftype,
                               version=ver, submit_at=now - timedelta(days=idx + 1), plagiarism_rate=rate,
                               plagiarism_status=pstat, status=st,
                               reviewer=advisors[sid_idx % 3] if st == "APPROVED" else None))

    # 答辩组：1 可发布 + 1 有冲突 + 1 未安排完整
    db.add_all([
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 1 组", defense_date="2026-07-08 09:00",
                               location="实训楼 B401", chair="周正邦（教授）",
                               members_json=["孙晓梅", "外聘 · 华信智能 陈总监"], secretary="林小婉",
                               student_count=12, conflict=None, published=False),
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 2 组", defense_date="2026-07-08 14:00",
                               location="实训楼 B402", chair="王芳（副教授）",
                               members_json=["王芳", "钱立群"], secretary="孙晓梅", student_count=10,
                               conflict="评委含指导教师本人，存在回避冲突", published=False),
        GraduationDefenseGroup(tenant_id=tenant_id, group_name="第 3 组", defense_date="2026-07-09 09:00",
                               location="待定", chair="待指定", members_json=["孙晓梅"], secretary="待指定",
                               student_count=8, conflict=None, published=False),
    ])
    db.add(GraduationAuditTrail(tenant_id=tenant_id, biz_type="RECORD", biz_id=str(stus[0].id),
                                action="导入毕设台账", operator="系统", detail="批量导入 10 名毕设学生",
                                occurred_at=now - timedelta(days=30)))
    db.commit()
    return {"students": len(stus), "topics": 5, "proposals": 5, "finals": 3, "defenseGroups": 3}
