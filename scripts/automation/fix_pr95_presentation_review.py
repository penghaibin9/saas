from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


# P1: deep-link identifiers are opaque Snowflake/BIGINT strings. Never round-trip through JS Number.
replace_once(
    "frontend/src/modules/messageCenter/views/MessageComposeView.vue",
    "        params[key] = /^\\d+$/.test(value) ? Number(value) : value\n",
    "        params[key] = value\n",
)

# P2: student employment follow-up table must bind to the real {way, content, time} DTO
# while translating the known way enum to business Chinese.
replace_once(
    "student-portal/src/views/employment/EmploymentView.vue",
    "const FOLLOW_UP_COLS = [\n"
    "  { key: 'followUpAt', label: '回访时间' }, { key: 'contactType', label: '联系类型' },\n"
    "  { key: 'result', label: '回访结果' }, { key: 'note', label: '备注' }\n"
    "]\n",
    "const FOLLOW_UP_WAY = Object.freeze({ PHONE: '电话联系', FACE: '面谈', RECOMMEND: '岗位推荐', VISIT: '走访' })\n"
    "const FOLLOW_UP_COLS = [\n"
    "  { key: 'time', label: '回访时间' },\n"
    "  { key: 'way', label: '跟进方式', formatter: (value) => FOLLOW_UP_WAY[String(value || '').toUpperCase()] || '其他方式' },\n"
    "  { key: 'content', label: '回访内容' }\n"
    "]\n",
)

# P1: major-split volunteer DTO is {choices, gpa, resultMajorId, resultChoiceRank,
# adjustReason, status}. Do not invent batch/name fields or expose raw DB IDs.
replace_once(
    "student-portal/src/views/academic/AcademicView.vue",
    "const SPLIT_COLS = [\n"
    "  { key: 'batchName', label: '分流批次' }, { key: 'choiceOrder', label: '志愿顺序' },\n"
    "  { key: 'majorName', label: '志愿专业' }, { key: 'status', label: '状态' },\n"
    "  { key: 'resultMajorName', label: '分流结果' }\n"
    "]\n",
    "const SPLIT_STATUS = Object.freeze({\n"
    "  PENDING: '待分配', ALLOCATED: '已完成分配', ADJUSTED: '已完成调剂',\n"
    "  CONFIRMED: '已确认', UNALLOCATED: '待人工调剂'\n"
    "})\n"
    "const SPLIT_COLS = [\n"
    "  { key: 'choices', label: '已填志愿', formatter: (value) => Array.isArray(value) && value.length ? `${value.length} 个志愿` : '—' },\n"
    "  { key: 'gpa', label: '分流参考绩点' },\n"
    "  { key: 'status', label: '状态', formatter: (value) => SPLIT_STATUS[String(value || '').toUpperCase()] || '状态待确认' },\n"
    "  { key: 'resultChoiceRank', label: '分流结果', formatter: (value, row) => {\n"
    "    if (row?.resultMajorId) return value ? `第 ${value} 志愿录取` : '已完成分配'\n"
    "    return String(row?.status || '').toUpperCase() === 'UNALLOCATED' ? '待人工调剂' : '待公布'\n"
    "  } },\n"
    "  { key: 'adjustReason', label: '调剂说明' }\n"
    "]\n",
)

write(
    "frontend/tests/message-deep-link-id-contract.test.mjs",
    """import assert from 'node:assert/strict'\nimport { readFileSync } from 'node:fs'\nimport test from 'node:test'\n\nconst source = readFileSync(new URL('../src/modules/messageCenter/views/MessageComposeView.vue', import.meta.url), 'utf8')\n\ntest('消息深链业务 ID 始终按不透明字符串传递', () => {\n  assert.doesNotMatch(source, /Number\\(value\\)/)\n  assert.doesNotMatch(source, /parseInt\\(value/)\n  assert.match(source, /params\\[key\\] = value/)\n})\n""",
)

write(
    "student-portal/tests/ui-presentation-v3-data-contract.test.mjs",
    """import assert from 'node:assert/strict'\nimport { readFileSync } from 'node:fs'\nimport test from 'node:test'\n\nconst employment = readFileSync(new URL('../src/views/employment/EmploymentView.vue', import.meta.url), 'utf8')\nconst academic = readFileSync(new URL('../src/views/academic/AcademicView.vue', import.meta.url), 'utf8')\n\ntest('就业回访表绑定真实 DTO 并把跟进方式业务化', () => {\n  const block = employment.match(/const FOLLOW_UP_COLS = \\[[\\s\\S]*?\\n\\]/)?.[0] || ''\n  assert.match(block, /key: 'time'/)\n  assert.match(block, /key: 'way'/)\n  assert.match(block, /key: 'content'/)\n  assert.doesNotMatch(block, /followUpAt|contactType|result|note/)\n  assert.match(employment, /PHONE: '电话联系'/)\n})\n\ntest('专业分流表只使用真实志愿 DTO 且不展示数据库 ID', () => {\n  const block = academic.match(/const SPLIT_COLS = \\[[\\s\\S]*?\\n\\]/)?.[0] || ''\n  assert.match(block, /key: 'choices'/)\n  assert.match(block, /key: 'gpa'/)\n  assert.match(block, /key: 'resultChoiceRank'/)\n  assert.match(block, /key: 'adjustReason'/)\n  assert.doesNotMatch(block, /batchName|choiceOrder|majorName|resultMajorName/)\n  assert.doesNotMatch(block, /key: 'resultMajorId'/)\n})\n""",
)
