"""培养方案 R7 质量门禁真库夹具。

当前正式提交门禁要求：
- requirement_json 中存在分模块学分结构；
- 至少一条 ACTIVE 的结构化毕业要求。

本模块只为历史端到端测试补齐这两个当前生产前置事实，不绕过质量校验，也不修改生产服务。
"""
from __future__ import annotations

import json

TID = 1000000000000000001


def seed_program_quality_requirements(program_id, *, total_credits, module="专业核心"):
    from app.db.session import get_sessionmaker
    from app.models import AaProgram, AaProgramGraduationRequirement

    db = get_sessionmaker()()
    try:
        program = db.get(AaProgram, int(program_id))
        assert program is not None and int(program.tenant_id) == TID
        program.requirement_json = json.dumps({
            "creditStructure": [{"module": module, "creditTarget": float(total_credits)}],
        }, ensure_ascii=False)
        existing = db.query(AaProgramGraduationRequirement).filter(
            AaProgramGraduationRequirement.tenant_id == TID,
            AaProgramGraduationRequirement.program_id == int(program_id),
            AaProgramGraduationRequirement.status == "ACTIVE",
            AaProgramGraduationRequirement.is_deleted.is_(False),
        ).first()
        if existing is None:
            db.add(AaProgramGraduationRequirement(
                tenant_id=TID,
                program_id=int(program_id),
                category="ABILITY",
                content="完成培养方案规定课程并达到毕业能力要求",
                sort_order=1,
                status="ACTIVE",
            ))
        db.commit()
    finally:
        db.close()
