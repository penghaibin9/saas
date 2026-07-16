"""学籍信息更正·证明材料附件（t_aa_student_correction 加列 material_file_ids）。

合规背景（R3 外部法规核验后补建，非产品增强）：学籍信息更正必须留存证明材料，是国家办法条文
的硬性要求，不是可选的产品决策——
  ·《中等职业学历教育学生学籍电子注册办法（试行）》教职成〔2014〕12号第十六条：「学生个人信息
    变更，学校在学生或监护人按有关规定提供相应证明后的10个工作日内，通过学生系统启动信息变更
    手续，**上传证明材料**，学校和学籍主管部门须依次在10个工作日内核办完成。」（本项目面向职业
    院校，中职直接适用本办法）；第十二条要求「将证明材料**归入学生学籍档案**」；第二十六条(二)
    对「因管理不善造成学生信息违规变更的」设追责条款。
  ·《普通高等学校学生管理规定》教育部令41号第三十四条（高职适用）：变更姓名、出生日期等证书需
    填写的个人信息，「应当有合理、充分的理由，并**提供有法定效力的相应证明文件**」。
  ·《全国中小学生学籍信息管理系统关键业务应用指南》教基一〔2014〕8号：身份证号/姓名/性别/
    出生日期为关键信息，变更「需提供**户籍部门出具**的证明材料」；非关键信息由学校直接维护。

字段级强制口径见 academic_affairs_service._CORRECTION_MATERIAL_REQUIRED：姓名/性别/证件号必填，
学号/年级选填（户籍部门无法为校内编码或学业属性出具证明，强制即不可用）。

nullable，历史行不受影响（此前无更正记录带附件）。幂等：inspect 判列。

Revision ID: aa_correction_material_r3
Revises: aa_resources_r3
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "aa_correction_material_r3"
down_revision = "aa_resources_r3"
branch_labels = None
depends_on = None

TABLE = "t_aa_student_correction"
COL = "material_file_ids"


def _cols(bind):
    insp = inspect(bind)
    if TABLE not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    if COL not in _cols(bind):
        op.add_column(TABLE, sa.Column(COL, sa.String(1000), nullable=True,
                                       comment="证明材料 file_id JSON 数组（关键身份字段必填）"))


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE not in inspect(bind).get_table_names():
        return
    if COL in _cols(bind):
        op.drop_column(TABLE, COL)
