const pool = require('../config/db');
const stipendModel = require('../models/stipendModel');
const guardianModel = require('../models/guardianModel');
const ai = require('../utils/ai');
const { success, error } = require('../utils/response');

// 容错聚合：单项失败不影响整体（不同部署模块/数据齐备度不一）
async function safeCount(sql, params = []) {
  try { const [[r]] = await pool.query(sql, params); return Number(r.c) || 0; } catch (_) { return null; }
}

const reportCenterController = {
  // 跨模块关键指标总览（管理员/教师）
  async overview(req, res) {
    try {
      if (![1, 2, 3].includes(req.user.role)) return error(res, '权限不足', 403);
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      const colWhere = collegeId ? ' AND college_id = ?' : '';
      const colParam = collegeId ? [collegeId] : [];

      const studentTotal = await safeCount(`SELECT COUNT(*) c FROM t_user WHERE role = 4 AND is_deleted = 0${colWhere}`, colParam);
      const interning = await safeCount(
        `SELECT COUNT(DISTINCT a.student_id) c FROM t_assignment a JOIN t_user u ON u.id = a.student_id
         WHERE a.is_deleted = 0 AND a.status = 1${collegeId ? ' AND u.college_id = ?' : ''}`, colParam);

      let stipend = null, guardian = null;
      try { stipend = await stipendModel.stats(collegeId ? { collegeId } : {}); } catch (_) {}
      try {
        const all = await guardianModel.findAll(collegeId ? { collegeId } : {}, { page: 1, pageSize: 1 });
        const signed = await guardianModel.findAll(collegeId ? { collegeId, status: 1 } : { status: 1 }, { page: 1, pageSize: 1 });
        guardian = { total: all.total, signed: signed.total, signedRate: all.total ? Math.round((signed.total / all.total) * 100) : null };
      } catch (_) {}

      return success(res, {
        scope: collegeId ? '本分院' : '全校',
        students: { total: studentTotal, interning },
        stipend, guardian,
        ai: ai.status(),
        generatedAt: new Date().toISOString(),
      }, '报表总览生成成功');
    } catch (e) { return error(res, '生成失败：' + e.message, 500); }
  },

  // 报表目录：列出系统内可下载/查看的报表及其入口（统一入口，便于一站式获取）
  async catalog(req, res) {
    return success(res, {
      reports: [
        { key: 'reporting', name: '实习数据标准报送包', desc: '面向省级/国家平台的标准字段映射导出', export: 'GET /api/reporting/export', roles: ['院校管理员', '分院管理员'] },
        { key: 'stipend', name: '实习报酬发放台账', desc: '报酬发放进度与不低于试用期80%合规率', view: 'GET /api/stipends/stats', roles: ['管理员', '指导教师'] },
        { key: 'guardian', name: '家长知情签署情况', desc: '监护人在线签署进度', view: 'GET /api/guardians', roles: ['管理员', '指导教师'] },
        { key: 'intern-handbook', name: '实习手册导出', desc: '实习监管手册', export: 'GET /api/benchmark/intern-handbook', roles: ['管理员'] },
        { key: 'gd-archive', name: '毕设档案导出', desc: '毕业设计档案', export: 'GET /api/benchmark/gd-archive', roles: ['管理员'] },
        { key: 'chsi', name: '学信网名单导出', desc: '学信网报送名单', export: 'GET /api/benchmark/chsi-export', roles: ['管理员'] },
        { key: 'analytics', name: '综合数据分析', desc: '多维统计与大屏数据', view: 'GET /api/analytics', roles: ['管理员'] },
      ],
    }, '报表目录');
  },
};

module.exports = reportCenterController;
