const express = require('express');
const { success } = require('../utils/response');
const { authMiddleware, requirePasswordChanged } = require('../middlewares/auth');

const userRoutes         = require('./userRoutes');
const adminUserRoutes    = require('./adminUserRoutes');
const collegeRoutes      = require('./collegeRoutes');
const majorRoutes        = require('./majorRoutes');
const classRoutes        = require('./classRoutes');
const enterpriseRoutes   = require('./enterpriseRoutes');
const positionRoutes     = require('./positionRoutes');
const applicationRoutes  = require('./applicationRoutes');
const reportRoutes       = require('./reportRoutes');
const statsRoutes        = require('./statsRoutes');
const notificationRoutes = require('./notificationRoutes');
const exportRoutes       = require('./exportRoutes');
const internPlanRoutes   = require('./internPlanRoutes');
const assignmentRoutes   = require('./assignmentRoutes');
const checkinRoutes      = require('./checkinRoutes');
const internLogRoutes    = require('./internLogRoutes');
const leaveRoutes        = require('./leaveRoutes');
const internStatsRoutes  = require('./internStatsRoutes');
const announcementRoutes = require('./announcementRoutes');
const gdTaskRoutes       = require('./gdTaskRoutes');
const gdTopicRoutes      = require('./gdTopicRoutes');
const gdGradeRoutes      = require('./gdGradeRoutes');
const gdAchievementRoutes = require('./gdAchievementRoutes');
const qualityCheckRoutes  = require('./qualityCheckRoutes');
const insuranceRoutes     = require('./insuranceRoutes');
const analyticsRoutes     = require('./analyticsRoutes');
const workbenchRoutes     = require('./workbenchRoutes');
const gdGuidanceRoutes    = require('./gdGuidanceRoutes');
const teacherRoutes       = require('./teacherRoutes');
const teacherRecordRoutes = require('./teacherRecordRoutes');
const satisfactionRoutes  = require('./satisfactionRoutes');
const agreementRoutes     = require('./agreementRoutes');
const riskRoutes          = require('./riskRoutes');
const defenseRoutes       = require('./defenseRoutes');
const enterpriseEvalRoutes = require('./enterpriseEvalRoutes');
const qualityReportRoutes  = require('./qualityReportRoutes');
const publicRoutes        = require('./publicRoutes');
const auditLogRoutes      = require('./auditLogRoutes');
const enterprisePortalRoutes = require('./enterprisePortalRoutes');
const complaintRoutes     = require('./complaintRoutes');
const systemConfigRoutes  = require('./systemConfigRoutes');
const workflowConfigRoutes = require('./workflowConfigRoutes');
const filingRoutes        = require('./filingRoutes');
const integrationRoutes   = require('./integrationRoutes');
const assignmentChangeRoutes = require('./assignmentChangeRoutes');
const benchmarkRoutes        = require('./benchmarkRoutes');
const { auditMiddleware } = require('../middlewares/audit');

const router = express.Router();

router.get('/health', (req, res) => {
  success(res, { timestamp: new Date().toISOString() }, 'API 服务正常');
});

// 全局操作审计：记录所有写操作的责任链（在响应结束后异步落库，不阻塞业务）
router.use(auditMiddleware);

// 用户自身相关(登录/注册/改密/个人信息)不受“强制改密”拦截
router.use('/users', userRoutes);
// 微信扫码登录（公开，登录前流程，不挂守卫）
router.use('/wechat', require('./wechatRoutes'));
// 公开免登录接口（企业导师评价等，凭 token）
router.use('/public', publicRoutes);
// 实时推送 SSE（令牌经查询串自校验，EventSource 无法带 header，故不挂标准守卫）
router.use('/realtime', require('./realtimeRoutes'));

// 其余业务接口：必须已登录且已完成首次改密
const guard = [authMiddleware, requirePasswordChanged];
router.use('/admin/users',   guard, adminUserRoutes);
router.use('/colleges',      guard, collegeRoutes);
router.use('/majors',        guard, majorRoutes);
router.use('/classes',       guard, classRoutes);
router.use('/enterprises',   guard, enterpriseRoutes);
router.use('/positions',     guard, positionRoutes);
router.use('/applications',  guard, applicationRoutes);
router.use('/reports',       guard, reportRoutes);
router.use('/stats',         guard, statsRoutes);
router.use('/notifications', guard, notificationRoutes);
router.use('/export',        guard, exportRoutes);
router.use('/intern-plans',  guard, internPlanRoutes);
router.use('/assignments',   guard, assignmentRoutes);
router.use('/checkins',      guard, checkinRoutes);
router.use('/intern-logs',   guard, internLogRoutes);
router.use('/leaves',        guard, leaveRoutes);
router.use('/intern-stats',  guard, internStatsRoutes);
router.use('/announcements', guard, announcementRoutes);
router.use('/gd-tasks',      guard, gdTaskRoutes);
router.use('/gd-topics',     guard, gdTopicRoutes);
router.use('/gd-grades',     guard, gdGradeRoutes);
router.use('/gd-achievements', guard, gdAchievementRoutes);
router.use('/quality-checks',  guard, qualityCheckRoutes);
router.use('/insurances',      guard, insuranceRoutes);
router.use('/analytics',       guard, analyticsRoutes);
router.use('/workbench',       guard, workbenchRoutes);
router.use('/gd-guidances',    guard, gdGuidanceRoutes);
router.use('/teacher',         guard, teacherRoutes);
router.use('/teacher-records', guard, teacherRecordRoutes);
router.use('/satisfaction',    guard, satisfactionRoutes);
router.use('/agreements',      guard, agreementRoutes);
router.use('/risk',            guard, riskRoutes);
router.use('/defense',         guard, defenseRoutes);
router.use('/enterprise-evals', guard, enterpriseEvalRoutes);
router.use('/quality-report',  guard, qualityReportRoutes);
router.use('/audit-logs',      guard, auditLogRoutes);
router.use('/enterprise-portal', guard, enterprisePortalRoutes);
router.use('/complaints',      guard, complaintRoutes);
router.use('/system-config',   systemConfigRoutes);
router.use('/workflow-config', workflowConfigRoutes);
router.use('/filings',         guard, filingRoutes);
router.use('/integration',     integrationRoutes);
router.use('/assignment-changes', guard, assignmentChangeRoutes);
router.use('/benchmark',           guard, benchmarkRoutes);
router.use('/ai',                  guard, require('./aiRoutes'));
router.use('/stipends',            guard, require('./stipendRoutes'));
router.use('/reporting',           guard, require('./reportingRoutes'));
router.use('/guardians',           guard, require('./guardianRoutes'));
router.use('/report-center',       guard, require('./reportCenterRoutes'));
router.use('/bigscreen',           guard, require('./bigscreenRoutes'));
router.use('/perm',                guard, require('./permRoutes'));
router.use('/workflows',           guard, require('./workflowRoutes'));

module.exports = router;
