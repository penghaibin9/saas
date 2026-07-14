/**
 * 04 学业过程中心 · 旧路由收敛（2026-07-15）。
 *
 * 旧 /admin/academic/* 6 个 partial 页与新 /admin/academic-affairs/* 并存造成双入口。
 * 按 CLAUDE.md §6.4「旧路由优先 redirect/alias，新链路完成后成为唯一主入口」：
 * 新教务中心模块已覆盖同域能力（读同一批 t_acad_* 底表），此处将旧路径 redirect 到新等价页，
 * 刷新不 404，主入口收敛到新。旧页面组件文件保留未删（可逆：移除 redirect 即恢复），
 * 待确认新页 100% 覆盖旧页专属查询后再评估删除组件（§6.4 删除前需引用核验+用户确认）。
 */
export const academicRoutes = {
  path: '/admin/academic',
  children: [
    { path: '', redirect: '/admin/academic-affairs' },                        // 学业总览 → 教务看板
    { path: 'students', redirect: '/admin/academic-affairs/roster' },         // 在籍学生 → 学籍名册
    { path: 'students/:id', redirect: '/admin/academic-affairs/roster' },
    { path: 'grades', redirect: '/admin/academic-affairs/grade-overview' },   // 课程成绩 → 成绩总览
    { path: 'credits', redirect: '/admin/academic-affairs/grade-overview' },  // 学分修读 → 成绩总览(含学分)
    { path: 'makeup-retake', redirect: '/admin/academic-affairs/makeup' },    // 补考重修 → 补考重修缓考免修控制台
    { path: 'warnings', redirect: '/admin/academic-affairs/warnings' },       // 学业预警 → 学业预警
    { path: 'warnings/:id', redirect: '/admin/academic-affairs/warnings' }
  ]
}

export default academicRoutes
