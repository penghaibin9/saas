"""教务增强对旧学业成绩/补考模型的增量映射。

``app.models.academic`` 保持当前 main 原样；本模块在模型聚合阶段为既有映射补充
稳定课程、教学班、名单版本和业务来源字段。这样主线继续修改旧学业域时，不会与
教务长期分支在同一个共享模型文件中产生文本冲突。
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import mapped_column

from app.models.academic import AcademicGrade, AcademicMakeup


def _add_column(model, name: str, column) -> None:
    if hasattr(model, name):
        return
    setattr(model, name, column)


def _append_unique(table, name: str, *columns: str) -> None:
    if any(getattr(item, "name", None) == name for item in table.constraints):
        return
    table.append_constraint(UniqueConstraint(*columns, name=name))


def _append_index(table, name: str, *columns: str) -> None:
    if any(getattr(item, "name", None) == name for item in table.indexes):
        return
    Index(name, *(table.c[column] for column in columns))


def install_academic_grade_extensions() -> None:
    _add_column(AcademicGrade, "course_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_aa_course.id，具体课程版本行"
    ))
    _add_column(AcademicGrade, "course_code", mapped_column(
        String(50), nullable=True, comment="课程代码快照"
    ))
    _add_column(AcademicGrade, "course_version", mapped_column(
        Integer, nullable=True, comment="课程库版本快照"
    ))
    _add_column(AcademicGrade, "attempt_no", mapped_column(
        Integer, nullable=True, comment="第几次修读；补考/清考继承原修读次数"
    ))
    _add_column(AcademicGrade, "grade_task_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_aa_grade_task"
    ))
    _add_column(AcademicGrade, "grade_record_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_aa_grade_record；正常发布来源唯一"
    ))
    _add_column(AcademicGrade, "source_biz_type", mapped_column(
        String(50), nullable=True, comment="MAKEUP/RECOGNITION/EXEMPTION等"
    ))
    _add_column(AcademicGrade, "source_biz_id", mapped_column(
        BigInteger, nullable=True, comment="业务来源记录ID"
    ))
    _add_column(AcademicGrade, "teaching_task_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_aa_teaching_task"
    ))
    _add_column(AcademicGrade, "teaching_class_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_aa_teaching_class"
    ))
    _add_column(AcademicGrade, "roster_version_id", mapped_column(
        BigInteger, nullable=True, comment="发布时采用的正式名单版本"
    ))
    _add_column(AcademicGrade, "effective_policy_code", mapped_column(
        String(80), nullable=True, comment="发布时冻结的有效成绩策略编码"
    ))
    _add_column(AcademicGrade, "effective_policy_version", mapped_column(
        Integer, nullable=True, comment="发布时冻结的有效成绩策略版本"
    ))
    _add_column(AcademicGrade, "effective_attempt_strategy", mapped_column(
        String(40), nullable=True, comment="LATEST_ATTEMPT/HIGHEST_SCORE/HIGHEST_PASSED/LATEST_PASSED等"
    ))
    _add_column(AcademicGrade, "pass_line_snapshot", mapped_column(
        Integer, nullable=True, comment="成绩发布时及格线快照"
    ))

    grade_table = AcademicGrade.__table__
    _append_unique(grade_table, "uk_acad_grade_source_record", "tenant_id", "grade_record_id")
    _append_unique(grade_table, "uk_acad_grade_source_biz", "tenant_id", "source_biz_type", "source_biz_id")
    _append_index(
        grade_table, "ix_acad_grade_course_attempt",
        "tenant_id", "acad_student_id", "course_id", "attempt_no", "record_status",
    )
    _append_index(grade_table, "ix_acad_grade_course_code", "tenant_id", "course_code", "course_version")
    _append_index(grade_table, "ix_acad_grade_grade_task", "tenant_id", "grade_task_id")
    _append_index(grade_table, "ix_acad_grade_teaching_task", "tenant_id", "teaching_task_id")
    _append_index(grade_table, "ix_acad_grade_teaching_class", "tenant_id", "teaching_class_id")
    _append_index(grade_table, "ix_acad_grade_source_biz", "tenant_id", "source_biz_type", "source_biz_id")

    _add_column(AcademicMakeup, "origin_grade_id", mapped_column(
        BigInteger, nullable=True, comment="→ t_acad_grade 原失败成绩"
    ))
    _add_column(AcademicMakeup, "source_biz_type", mapped_column(
        String(50), nullable=True, comment="DEFERRED_EXAM等原始业务"
    ))
    _add_column(AcademicMakeup, "source_biz_id", mapped_column(BigInteger, nullable=True))
    _add_column(AcademicMakeup, "course_id", mapped_column(
        BigInteger, nullable=True, comment="具体课程版本"
    ))
    _add_column(AcademicMakeup, "course_code", mapped_column(String(50), nullable=True))
    _add_column(AcademicMakeup, "course_version", mapped_column(Integer, nullable=True))
    _add_column(AcademicMakeup, "attempt_no", mapped_column(
        Integer, nullable=True, comment="补考继承原修读次数；缓考冻结当前修读次数"
    ))
    _add_column(AcademicMakeup, "teaching_task_id", mapped_column(BigInteger, nullable=True))
    _add_column(AcademicMakeup, "teaching_class_id", mapped_column(BigInteger, nullable=True))
    _add_column(AcademicMakeup, "roster_version_id", mapped_column(BigInteger, nullable=True))

    makeup_table = AcademicMakeup.__table__
    _append_unique(makeup_table, "uk_acad_makeup_source_biz", "tenant_id", "source_biz_type", "source_biz_id")
    _append_index(makeup_table, "ix_acad_makeup_origin_grade", "tenant_id", "origin_grade_id")
    _append_index(
        makeup_table, "ix_acad_makeup_course_attempt",
        "tenant_id", "acad_student_id", "course_id", "attempt_no",
    )
    _append_index(makeup_table, "ix_acad_makeup_teaching_task", "tenant_id", "teaching_task_id")
    _append_index(makeup_table, "ix_acad_makeup_roster_version", "tenant_id", "roster_version_id")


install_academic_grade_extensions()
