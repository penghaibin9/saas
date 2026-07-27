"""学生 PC 门户 · 服务层。"""

# 最终安全门面：成绩只生成查询件；评教使用正式教学班名单、稳定学生身份和匿名幂等提交。
from . import academic_evaluation_safety_facade as academic_service

__all__ = ["academic_service"]
