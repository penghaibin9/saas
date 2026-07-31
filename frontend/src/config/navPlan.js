import NAV_PLAN from './navPlan.base.js'

/**
 * 学工菜单权限投影收口层。
 *
 * 路由守卫与后端能力是权限单一事实源：
 * - 数字迎新入口跟随 orientationRoutes 的 orientation.student.view；
 * - 班级管理入口跟随 campusServiceRoutes 的 campus.record.view。
 *
 * 其余导航结构和导出全部保留在 navPlan.base.js，本层只修正两个历史菜单投影偏差。
 */
const studentAffairs = NAV_PLAN.find((group) => group.key === 'student-affairs')

const orientation = studentAffairs?.children?.find((item) => item.key === 'sa-orientation')
if (orientation) orientation.permissionKey = 'orientation.student.view'

const classModule = studentAffairs?.children?.find((item) => item.key === 'sa-classes')
const classManagement = classModule?.children?.find(
  (item) => item.path === '/admin/campus-service/classes'
)
if (classManagement) classManagement.permissionKey = 'campus.record.view'

export * from './navPlan.base.js'
export default NAV_PLAN
