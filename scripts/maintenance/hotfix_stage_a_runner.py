#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

runner = Path(__file__).with_name("apply_miniapp_stage_a.py")
source = runner.read_text(encoding="utf-8")

pattern = re.compile(
    r'''text = replace_once\(\n'''
    r'''    text,\n'''
    r'''    "export const mobileTeacherTodos = \(\) => realRequest\('/mobile/teacher/todos'\)\\n",\n'''
    r'''.*?'''
    r'''    "real API teacher pages",\n'''
    r'''\)''',
    re.S,
)

replacement = r'''text = replace_once(
    text,
    "/* 教师端·工作台：真实摘要、真实待办、真实风险；任一主摘要失败必须显式报错，不回落 mock。 */",
    """/* 教师端·移动聚合兼容导出 */
export const mobileTeacherOverview = () => realRequest('/mobile/teacher/overview')
export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')
export const mobileTeacherDomain = (domain) => realRequest('/mobile/teacher/' + domain)
export const teacherTodosPage = (group = 'all', page = 1, pageSize = 20) =>
  realRequest(`/mobile/teacher/todos-page?group=${encodeURIComponent(group)}&page=${page}&pageSize=${pageSize}`)
export const teacherRiskStudentsPage = (level = 'all', page = 1, pageSize = 20) =>
  realRequest(`/mobile/teacher/risk-students-page?level=${encodeURIComponent(level)}&page=${page}&pageSize=${pageSize}`)
    .then((data) => ({
      ...data,
      list: (data.list || []).map((student) => ({
        ...student,
        risk: student.riskLevel || 'MEDIUM',
        task: student.reason || student.riskType || '风险事项待处理',
        pending: 1,
        last: student.latestTime || '',
        stage: student.riskType || ''
      }))
    }))

/* 教师端·工作台：真实摘要、真实待办、真实风险；任一主摘要失败必须显式报错，不回落 mock。 */""",
    "real API teacher pages",
)'''

updated, count = pattern.subn(replacement, source, count=1)
if count != 1:
    raise RuntimeError(f"failed to hotfix teacher page anchor: matches={count}")
runner.write_text(updated, encoding="utf-8")
print("stage A runner anchor hotfixed")
