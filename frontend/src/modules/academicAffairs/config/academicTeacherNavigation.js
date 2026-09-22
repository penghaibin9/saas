/**
 * ACADEMIC_TEACHER 专属教务导航投影。
 *
 * 只重组已有真实页面并保留公共 BasePortalLayout / TeacherWorkspaceFrame 壳。
 * 安全授权仍由 route meta + 后端对象级 Authority 决定。
 */
const ROLE = 'ACADEMIC_TEACHER'

const GROUPS = [
  {
    key: 'aa-teacher-my-teaching', label: '我的教学', entries: [
      { leafId: 'aa.schedule.schedule.teacher', label: '今日教学', path: '/admin/academic-affairs/teacher/today' },
      { leafId: 'aa.teaching-tasks.teaching.tasks.teacher.confirm', label: '教学任务确认' }
    ]
  },
  {
    key: 'aa-teacher-my-schedule', label: '我的课表', entries: [
      { leafId: 'aa.schedule.schedule.teacher', label: '个人课表', path: '/admin/academic-affairs/schedule/teacher' },
      { leafId: 'aa.schedule-change.schedule.change.apply', label: '调停课申请' },
      { leafId: 'aa.schedule-change.schedule.change', label: '我的调停课记录' }
    ]
  },
  {
    key: 'aa-teacher-schedule-query', label: '课表查询', entries: [
      { leafId: 'aa.schedule.schedule.class', label: '班级课表' },
      { leafId: 'aa.schedule.schedule.room', label: '教室课表' },
      { leafId: 'aa.schedule.schedule.teaching.class', label: '教学班课表' },
      { leafId: 'aa.schedule.schedule.week', label: '周课表' },
      { leafId: 'aa.schedule.schedule.semester', label: '学期课表' }
    ]
  },
  {
    key: 'aa-teacher-grade-attendance', label: '成绩与考勤', entries: [
      { leafId: 'aa.grades.grade.entry', label: '成绩录入与提交' },
      { leafId: 'aa.grade-review.grade.change', label: '成绩更正申请' },
      { leafId: 'aa.attendance.attendance.stats', label: '课堂考勤统计' },
      { leafId: 'aa.attendance.attendance.stats.panel.sessions', label: '考勤场次查询' }
    ]
  },
  {
    key: 'aa-teacher-textbook-resource', label: '教材与资源', entries: [
      { leafId: 'aa.textbooks.textbooks.tab.selection', label: '教材选用', permissionKey: 'academicAffairs.textbook.selection.manage' },
      { leafId: 'aa.resources.classroom.bookings', label: '教室预约' },
      { leafId: 'aa.resources.resources.lab.bookings', label: '实训室预约' },
      { leafId: 'aa.resources.resources.occupancy', label: '资源占用查询' }
    ]
  },
  {
    key: 'aa-teacher-materials', label: '教学资料', entries: [
      { leafId: 'aa.training.programs', label: '培养方案' },
      { leafId: 'aa.courses.courses', label: '课程库' }
    ]
  }
]

function roleCode(ctx) {
  return String(ctx?.currentRole?.roleCode || ctx?.currentRole?.roleType || '').toUpperCase()
}
function refParts(ref) {
  const raw = String(ref || '').split('#')[0]
  const index = raw.indexOf('?')
  const path = index >= 0 ? raw.slice(0, index) : raw
  const query = new URLSearchParams(index >= 0 ? raw.slice(index + 1) : '')
  return { path: path.replace(/\/$/, '') || '/', query }
}
function querySubset(expected, actual) {
  for (const [key, value] of expected.entries()) if (actual.get(key) !== value) return false
  return true
}
function leafIndex(modules) {
  const index = new Map()
  for (const mod of modules || []) for (const leaf of mod.children || []) {
    if (leaf?.leafId && !index.has(leaf.leafId)) index.set(leaf.leafId, leaf)
  }
  return index
}
function projectedLeaf(source, spec, groupKey) {
  if (!source) return null
  return {
    ...source,
    label: spec.label || source.label,
    path: spec.path || source.path,
    ...(spec.permissionKey ? { permissionKey: spec.permissionKey } : {}),
    teacherProjectionId: `${groupKey}:${spec.leafId}:${spec.label || source.label}`,
    sourceLeafId: source.leafId,
    searchAliases: [...new Set([spec.label || source.label, ...(source.searchAliases || [])])]
  }
}
export function isAcademicTeacherContext(ctx) { return roleCode(ctx) === ROLE }
export function academicTeacherDefaultPath(ctx) {
  return isAcademicTeacherContext(ctx) ? '/admin/academic-affairs/teacher/today' : ''
}
export function projectAcademicTeacherModules(modules, ctx) {
  if (!isAcademicTeacherContext(ctx)) return modules || []
  const index = leafIndex(modules)
  return GROUPS.map(group => {
    const children = group.entries.map(spec => projectedLeaf(index.get(spec.leafId), spec, group.key)).filter(Boolean)
    return { key: group.key, label: group.label, path: children[0]?.path || '', status: 'implemented', disabled: false, badge: '', entryType: 'CONTAINER', children }
  }).filter(group => group.children.length)
}
export function academicTeacherActiveModule(modules, navRef, ctx) {
  if (!isAcademicTeacherContext(ctx)) return ''
  const current = refParts(navRef)
  let best = { key: '', score: -1 }
  for (const mod of modules || []) for (const leaf of mod.children || []) {
    if (!leaf.path) continue
    const target = refParts(leaf.path)
    const pathMatch = current.path === target.path || current.path.startsWith(`${target.path}/`)
    if (!pathMatch || !querySubset(target.query, current.query)) continue
    const score = [...target.query.keys()].length * 1000 + target.path.length
    if (score > best.score) best = { key: mod.key, score }
  }
  return best.key
}
export function filterAcademicTeacherSearchResults(results, ctx, modules) {
  if (!isAcademicTeacherContext(ctx)) return results || []
  const projected = projectAcademicTeacherModules(modules || [], ctx)
  const allowed = projected.flatMap(mod => mod.children || []).map(leaf => refParts(leaf.path))
  return (results || []).filter(item => {
    if (item.kind === '学生') return false
    if (!item.to) return true
    const target = refParts(item.to)
    const academic = target.path === '/admin/academic' || target.path.startsWith('/admin/academic/') ||
      target.path === '/admin/academic-affairs' || target.path.startsWith('/admin/academic-affairs/')
    if (!academic) return true
    return allowed.some(row => target.path === row.path || target.path.startsWith(`${row.path}/`))
  })
}
export const ACADEMIC_TEACHER_MENU_SPEC = GROUPS
