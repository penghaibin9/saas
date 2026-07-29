#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

runner = Path(__file__).with_name("apply_miniapp_stage_a.py")
source = runner.read_text(encoding="utf-8")

old_regex_helper = "    new, count = re.subn(pattern, replacement, text, count=1, flags=flags)\n"
new_regex_helper = "    new, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=flags)\n"
if source.count(old_regex_helper) != 1:
    raise RuntimeError(f"regex helper matches={source.count(old_regex_helper)}")
source = source.replace(old_regex_helper, new_regex_helper, 1)

old_teacher = '''text = replace_once(
    text,
    "export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')\\n",
    """export const mobileTeacherTodos = () => realRequest('/mobile/teacher/todos')
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
""",
    "real API teacher pages",
)'''
new_teacher = '''text = replace_once(
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
if source.count(old_teacher) != 1:
    raise RuntimeError(f"teacher patch block matches={source.count(old_teacher)}")
source = source.replace(old_teacher, new_teacher, 1)

old_message = '''text = replace_once(
    text,
    """/** 本人消息详情（按 messageId，杀进程后仍可重开） */
export const getMessageDetail = (id) =>
""",
    """export const selfMessagesPage = (tab = 'todo', page = 1, pageSize = 20) =>
  realRequest(`/mobile/me/messages-page?tab=${encodeURIComponent(tab)}&page=${page}&pageSize=${pageSize}`)

/** 本人消息详情（按 messageId，杀进程后仍可重开） */
export const getMessageDetail = (id) =>
""",
    "real API student messages page",
)'''
new_message = '''text = replace_once(
    text,
    """export const getMessageDetail = (id) =>
""",
    """export const selfMessagesPage = (tab = 'todo', page = 1, pageSize = 20) =>
  realRequest(`/mobile/me/messages-page?tab=${encodeURIComponent(tab)}&page=${page}&pageSize=${pageSize}`)

export const getMessageDetail = (id) =>
""",
    "real API student messages page",
)'''
if source.count(old_message) != 1:
    raise RuntimeError(f"message patch block matches={source.count(old_message)}")
source = source.replace(old_message, new_message, 1)

old_summary_apply = 'text = replace_once(text, old_result_notice, new_result_notice, "student message summary result")'
new_summary_apply = '''text = regex_once(
    text,
    r''' + "'''" + r'''            "notices": \[.*?            "unreadCount": unread_count,\n''' + "'''" + r''',
    new_result_notice,
    "student message summary result",
)'''
if source.count(old_summary_apply) != 1:
    raise RuntimeError(f"summary apply matches={source.count(old_summary_apply)}")
source = source.replace(old_summary_apply, new_summary_apply, 1)

runner.write_text(source, encoding="utf-8")
print("stage A runner anchors hotfixed")
