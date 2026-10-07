// The complete catalog and every permission remain intact; this is a daily UI projection.
const ORDER = ['aa-dashboard', 'aa-training', 'aa-teaching-tasks', 'aa-schedule', 'aa-daily', 'aa-exam', 'aa-grades', 'aa-textbooks', 'aa-resources', 'aa-student-status', 'aa-stats', 'aa-archive']
const TITLES = { 'aa-dashboard': '本学院工作台', 'aa-training': '培养方案与课程', 'aa-teaching-tasks': '本学院教学任务', 'aa-schedule': '专业课排课与课表', 'aa-daily': '课表与调停课', 'aa-grades': '成绩审核', 'aa-stats': '本学院统计', 'aa-archive': '归档准备' }
const SCHOOL_ONLY = new Set([
  'aa.training.programs.console.tab.publish', 'aa.schedule.schedule.publish',
  'aa.grade-review.grade.publish', 'aa.calendar.calendar.tab.publish',
  'aa.terms.terms.current', 'aa.terms.terms.teaching.weeks', 'aa.terms.terms.status'
])

export function isAcademicCollegeContext(ctx) {
  const role = String(ctx?.currentRole?.roleCode || ctx?.currentRole?.roleType || '').toUpperCase()
  return role === 'COLLEGE_ADMIN'
}
export function projectAcademicCollegeModules(modules, ctx) {
  if (!isAcademicCollegeContext(ctx)) return modules || []
  return (modules || []).map(mod => {
    const children = (mod.children || []).map(leaf => ({
      ...leaf,
      label: leaf.leafId === 'aa.dashboard.overview' ? '本学院教学运行' : leaf.label,
      menuSecondary: leaf.menuSecondary || SCHOOL_ONLY.has(leaf.leafId) || mod.key === 'aa-terms'
    }))
    return { ...mod, label: TITLES[mod.key] || mod.label, children,
      path: children.find(leaf => !leaf.hidden && !leaf.menuSecondary)?.path || mod.path }
  }).sort((a, b) => {
    const rank = key => ORDER.includes(key) ? ORDER.indexOf(key) : ORDER.length
    return rank(a.key) - rank(b.key)
  })
}
