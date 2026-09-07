// Same visual tokens as the accepted student workspace. No student/teacher business state is shared.
export const WORKSPACE_THEMES = [
  { key: 'dark', label: '曜石黑', bg: '#151619', surface: '#202126', header: '#1b1c20', soft: '#292d38', line: '#34363f', accent: '#95b1ff', ink: '#e9ecf3', muted: '#aeb6c6', on: '#162039' },
  { key: 'blue', label: '雾蓝', bg: '#f4f7fc', surface: '#ffffff', header: '#edf3fc', soft: '#e5edfc', line: '#dce5f3', accent: '#285bb5', ink: '#203450', muted: '#586d89', on: '#ffffff' },
  { key: 'sage', label: '护眼绿', bg: '#f0f4ed', surface: '#fbfcf8', header: '#f7faf3', soft: '#e2eee4', line: '#d5e1d2', accent: '#347254', ink: '#243c31', muted: '#536d5d', on: '#ffffff' },
  { key: 'plum', label: '石墨紫', bg: '#f3f3f6', surface: '#ffffff', header: '#f4f1f8', soft: '#eae4f4', line: '#e0daeb', accent: '#6954a3', ink: '#302d42', muted: '#6b617e', on: '#ffffff' }
]
export const WORKSPACE_TONES = {
  blue: { label: '学院蓝', value: '#3269bf' }, sage: { label: '青竹绿', value: '#27968d' },
  plum: { label: '藤花紫', value: '#8461bc' }, amber: { label: '麦穗金', value: '#b57f24' },
  cyan: { label: '湖水蓝', value: '#278eb0' }, coral: { label: '陶土红', value: '#bf6b59' }
}
export const WORKSPACE_ICON_KEYS = ['document', 'user', 'calendar', 'house', 'flag', 'bell', 'message', 'monitor', 'folder', 'records', 'star', 'school']
export function shortcutAppearance(page, appearances = {}) {
  const text = `${page?.path || ''} ${page?.title || ''}`
  let icon = 'document', color = 'blue'
  if (/待办|approval/.test(text)) { icon = 'document'; color = 'amber' }
  else if (/请假|销假|leave/.test(text)) { icon = 'calendar'; color = 'sage' }
  else if (/宿舍|住宿|dorm/.test(text)) { icon = 'house'; color = 'plum' }
  else if (/迎新|orientation/.test(text)) { icon = 'flag'; color = 'cyan' }
  else if (/风险|预警|risk/.test(text)) { icon = 'bell'; color = 'coral' }
  else if (/学生|student\/list/.test(text)) icon = 'user'
  else if (/消息|message/.test(text)) icon = 'message'
  else if (/工作台|看板|总览|workbench/.test(text)) icon = 'monitor'
  else if (/班级|classes/.test(text)) icon = 'school'
  else if (/档案|material/.test(text)) icon = 'folder'
  else if (/奖|助|funding|aid/.test(text)) icon = 'star'
  const saved = appearances[page?.id] || {}
  return { label: typeof saved.label === 'string' ? saved.label.trim().slice(0, 16) : '', icon: WORKSPACE_ICON_KEYS.includes(saved.icon) ? saved.icon : icon, color: Object.hasOwn(WORKSPACE_TONES, saved.color) ? saved.color : color }
}
export function workspaceTokens(key) {
  const t = WORKSPACE_THEMES.find(t => t.key === key) || WORKSPACE_THEMES[1]
  return {
    'color-scheme': t.key === 'dark' ? 'dark' : 'light',
    '--bg': t.bg, '--bg-page': t.bg, '--bg-card': t.surface, '--bg-sidebar': t.header,
    '--card': t.surface, '--card-b': t.line, '--dv': t.line, '--topbar-bg': t.header, '--topbar-bd': t.line,
    '--bg-elevated': t.surface, '--bg-section': t.header, '--bg-subtle': t.header, '--bg-hover': t.soft,
    '--border-base': t.line, '--border-light': t.line, '--card-border': t.line,
    '--g1': t.accent, '--g2': t.accent, '--pri-h': t.accent, '--pri-500': t.accent,
    '--btn-p-bg': t.accent, '--btn-p-bg-h': t.accent, '--btn-p-shadow': 'none',
    '--surface': t.surface, '--surface-2': t.header, '--field-bg': t.header,
    '--pri': t.accent, '--pri-text': t.accent, '--pri-display': t.accent, '--pri-on': t.on,
    '--pri-bg': t.soft, '--pri-50': t.soft, '--pri-100': t.soft, '--line': t.line, '--line2': t.line,
    '--t1': t.ink, '--t2': t.ink, '--t3': t.muted, '--t4': t.muted,
    '--text-primary': t.ink, '--text-secondary': t.muted, '--text-tertiary': t.muted,
    '--text-disabled': t.muted, '--text-link': t.accent, '--text-inverse': t.on,
    '--primary-100': t.soft, '--primary-500': t.accent, '--primary-600': t.accent, '--primary-700': t.accent,
    '--hc-topbar-bg': t.header, '--hc-topbar-border': t.line, '--hc-topbar-text': t.ink,
    '--hc-topbar-muted': t.muted, '--hc-topbar-control-bg': t.surface, '--hc-topbar-control-hover': t.soft,
    '--hc-topbar-control-border': t.line, '--hc-topbar-control-text': t.muted, '--hc-topbar-shadow': 'none',
    '--el-bg-color': t.surface, '--el-bg-color-overlay': t.surface, '--el-fill-color-blank': t.surface,
    '--el-fill-color-light': t.header, '--el-fill-color': t.soft, '--el-fill-color-lighter': t.header,
    '--el-text-color-primary': t.ink, '--el-text-color-regular': t.muted, '--el-text-color-secondary': t.muted,
    '--el-text-color-placeholder': t.muted, '--el-disabled-text-color': t.muted,
    '--el-border-color': t.line, '--el-border-color-light': t.line, '--el-border-color-lighter': t.line,
    '--el-color-primary': t.accent, '--el-color-primary-light-9': t.soft, '--el-color-primary-light-8': t.soft,
    '--border-color': t.line, '--color-primary': t.accent, '--primary-50': t.soft, '--primary-25': t.header,
    '--s1': '0 1px 2px #10203008', '--s2': '0 2px 8px #10203010', '--r': '10px', '--rs': '6px'
  }
}
export function workspacePages(modules) {
  return modules.flatMap(mod => (mod.children?.length ? mod.children : [mod])
    .filter(item => item.path && !item.disabled)
    .map(item => ({ ...item, id: item.path, title: item.label, moduleKey: mod.key, trail: mod.label })))
}
// 菜单参数是页面身份，批次/分页等额外参数不应破坏高亮。
export function workspaceCurrentPage(pages, fullPath, activeModule = '') {
  const current = new URL(fullPath, 'https://workspace.invalid')
  let best, bestScore = -1
  for (const page of pages) {
    for (const path of [page.path, ...(page.workspacePaths || [])]) {
    const candidate = new URL(path, 'https://workspace.invalid')
    const exact = current.pathname === candidate.pathname
    if (!exact && !current.pathname.startsWith(candidate.pathname + '/')) continue
    const query = [...candidate.searchParams]
    const matches = query.every(([key, value]) => current.searchParams.get(key) === value)
    const score = candidate.pathname.length * 10 + (exact ? 1 : 0) + (matches ? query.length * 10000 : 0)
    if (score > bestScore) { best = page; bestScore = score }
    }
  }
  return best || pages.find(page => page.moduleKey === activeModule && !page.workspaceHidden)
}
export function defaultShortcutIds(pages) {
  const paths = ['/admin/approval/todos', '/admin/student/list', '/admin/student-affairs/leave', '/admin/student-affairs/dorm', '/admin/orientation', '/admin/student-affairs/risk', '/admin/student-affairs/funding']
  const ids = paths.map(path => pages.find(page => page.path === path)?.id).filter(Boolean)
  return ids.length ? ids : pages.slice(0, 4).map(page => page.id)
}
export function restoreWorkspace(value, pages) {
  const saved = value && typeof value === 'object' ? value : {}
  const allowed = new Set(pages.map(item => item.id))
  const safeIds = (ids, max) => Array.isArray(ids) ? [...new Set(ids.filter(id => allowed.has(id)))].slice(0, max) : []
  const appearance = {}
  for (const id of allowed) {
    const entry = saved.appearance?.[id]
    if (!entry || typeof entry !== 'object') continue
    appearance[id] = shortcutAppearance(pages.find(page => page.id === id), saved.appearance)
  }
  return {
    appearance,
    recent: safeIds(saved.recent, 30),
    second: ['compact', 'full', 'auto'].includes(saved.second) ? saved.second : 'compact',
    third: ['compact', 'full', 'auto'].includes(saved.third) ? saved.third : 'compact',
    theme: WORKSPACE_THEMES.some(t => t.key === saved.theme) ? saved.theme : 'blue',
    tabs: safeIds(saved.tabs, 20), shortcuts: Array.isArray(saved.shortcuts) ? safeIds(saved.shortcuts, 8) : defaultShortcutIds(pages),
    collapsed: saved.collapsed !== false
  }
}
const SHORT_NAMES = { 'sa-workbench': '工作', 'sa-profile': '学生', 'sa-classes': '班级', 'sa-orientation': '迎新', 'sa-leave': '请假', 'sa-dorm': '住宿', 'sa-risk': '风险', 'sa-difficulty': '认定', 'sa-aid': '奖助', 'sa-discipline': '处分', 'sa-talks': '家校', 'sa-mental': '心理', 'sa-activities': '活动', 'sa-archive-stats': '统计' }
const PAGE_SHORT_NAMES = { '我的工作台': '首页', '我的待办': '待办', '审批中心': '审批', '消息中心': '消息', '学工大屏': '大屏', '最近访问': '最近', '帮助中心': '帮助', '请假审批': '审批', '销假与续假': '返校', '请假台账': '台账', '请假统计': '统计', '认定批次': '批次', '认定申请与审核（工作台）': '评审', '公示待办': '公示', '认定台账': '台账', '困难学生库': '名册', '认定统计': '统计', '异议复核': '异议',
  '资助项目': '项目', '资助批次': '批次', '申请评审（工作台）': '评审', '公示申诉': '申诉', '发放台账': '发放', '资助统计': '统计', '助学金管理': '助学', '勤工助学': '勤工', '助学贷款': '贷款', '减免与临时补助': '减免' }
export function workspaceShort(item) { return SHORT_NAMES[item.key] || PAGE_SHORT_NAMES[item.label] || String(item.label || '').slice(0, 2) }
