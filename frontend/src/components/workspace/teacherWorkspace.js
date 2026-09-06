// Same visual tokens as the accepted student workspace. No student/teacher business state is shared.
export const WORKSPACE_THEMES = [
  { key: 'dark', label: '曜石黑', bg: '#151619', surface: '#202126', header: '#1b1c20', soft: '#292d38', line: '#34363f', accent: '#95b1ff', ink: '#e9ecf3', muted: '#aeb6c6', on: '#162039' },
  { key: 'blue', label: '雾蓝', bg: '#f4f7fc', surface: '#ffffff', header: '#edf3fc', soft: '#e5edfc', line: '#dce5f3', accent: '#285bb5', ink: '#203450', muted: '#586d89', on: '#ffffff' },
  { key: 'sage', label: '护眼绿', bg: '#f0f4ed', surface: '#fbfcf8', header: '#f7faf3', soft: '#e2eee4', line: '#d5e1d2', accent: '#347254', ink: '#243c31', muted: '#536d5d', on: '#ffffff' },
  { key: 'plum', label: '石墨紫', bg: '#f3f3f6', surface: '#ffffff', header: '#f4f1f8', soft: '#eae4f4', line: '#e0daeb', accent: '#6954a3', ink: '#302d42', muted: '#6b617e', on: '#ffffff' }
]
export const WORKSPACE_TONES = { blue: { label: '蓝色', value: '#326ac3' }, sage: { label: '绿色', value: '#278c7e' }, plum: { label: '紫色', value: '#8061b8' }, amber: { label: '琥珀', value: '#aa781f' } }
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
export function restoreWorkspace(value, pages) {
  const saved = value && typeof value === 'object' ? value : {}
  const allowed = new Set(pages.map(item => item.id))
  const safeIds = (ids, max) => Array.isArray(ids) ? [...new Set(ids.filter(id => allowed.has(id)))].slice(0, max) : []
  const appearance = {}
  for (const id of allowed) {
    const entry = saved.appearance?.[id]
    if (!entry || typeof entry !== 'object') continue
    appearance[id] = { label: typeof entry.label === 'string' ? entry.label.trim().slice(0, 12) : '', color: Object.hasOwn(WORKSPACE_TONES, entry.color) ? entry.color : 'blue' }
  }
  return {
    appearance,
    second: ['compact', 'full', 'auto'].includes(saved.second) ? saved.second : 'compact',
    third: ['compact', 'full', 'auto'].includes(saved.third) ? saved.third : 'compact',
    theme: WORKSPACE_THEMES.some(t => t.key === saved.theme) ? saved.theme : 'blue',
    tabs: safeIds(saved.tabs, 20), shortcuts: Array.isArray(saved.shortcuts) ? safeIds(saved.shortcuts, 8) : pages.filter(item => item.path.startsWith('/admin/student-affairs/leave')).slice(0, 4).map(item => item.id),
    collapsed: saved.collapsed !== false
  }
}
const SHORT_NAMES = { 'sa-workbench': '看板', 'sa-profile': '学生', 'sa-classes': '班级', 'sa-orientation': '迎新', 'sa-leave': '请假', 'sa-dorm': '住宿', 'sa-risk': '风险', 'sa-difficulty': '认定', 'sa-aid': '奖助', 'sa-discipline': '处分', 'sa-talks': '家校', 'sa-mental': '心理', 'sa-activities': '活动', 'sa-archive-stats': '统计' }
const PAGE_SHORT_NAMES = { '请假审批': '审批', '销假与续假': '返校', '请假台账': '台账', '请假统计': '统计', '认定批次': '批次', '认定申请与审核（工作台）': '评审', '公示待办': '公示', '认定台账': '台账', '困难学生库': '名册', '认定统计': '统计', '异议复核': '异议',
  '资助项目': '项目', '资助批次': '批次', '申请评审（工作台）': '评审', '公示申诉': '申诉', '发放台账': '发放', '资助统计': '统计', '助学金管理': '助学', '勤工助学': '勤工', '助学贷款': '贷款', '减免与临时补助': '减免' }
export function workspaceShort(item) { return SHORT_NAMES[item.key] || PAGE_SHORT_NAMES[item.label] || String(item.label || '').slice(0, 2) }
