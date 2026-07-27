"""学生 PC 门户 · 服务层。"""

# 统一从安全门面暴露教务服务：其余能力继续委托既有模块，成绩出件强制为查询件。
from . import academic_transcript_safety_facade as academic_service

__all__ = ["academic_service"]
