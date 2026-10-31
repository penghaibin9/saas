"""教务"本学院"办理岗位的角色集合（文档 2 R0）。

学院教务 COLLEGE_ACADEMIC 与旧学院管理员 COLLEGE_ADMIN 在教务域内走同一条"本学院"数据范围分支。
COLLEGE_ADMIN 拆除（D16，排在 R2 审批人模型之后）时只需从这里删掉它。
审核节点（学院审核人）不使用本集合，由 R2 的流程节点审批人判定。
"""
from __future__ import annotations

COLLEGE_ACADEMIC_ROLES = frozenset({"COLLEGE_ADMIN", "COLLEGE_ACADEMIC"})
