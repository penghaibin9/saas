/**
 * UI-P3 演示导航配置（仅演示环境使用）
 * 管理侧四个演示页共用一套左侧菜单；学生/企业门户各自使用门户壳默认菜单。
 */
export const adminDemoMenus = [
  { key: 'practice', label: '实践教学驾驶舱', icon: '▦', path: '/demo/practice-dashboard' },
  { key: 'gd', label: '毕业设计驾驶舱', icon: '◧', path: '/demo/graduation-design-dashboard' },
  { key: 'internship', label: '岗位实习驾驶舱', icon: '◨', path: '/demo/internship-dashboard' },
  { key: 'teacher', label: '教师工作台', icon: '◩', path: '/demo/teacher-workbench' },
  { key: 'student-portal', label: '学生门户（演示）', icon: '⌂', path: '/demo/student-portal' },
  {
    key: 'enterprise-portal',
    label: '企业门户（演示）',
    icon: '◇',
    path: '/demo/enterprise-workbench'
  }
]

export function navigateMenu(router, item) {
  if (item && item.path) router.push(item.path)
}
