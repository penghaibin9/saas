const auditLogModel = require('../models/auditLogModel');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

/**
 * 审计日志查询（仅管理员）。
 * 院校管理员(role=1)可查全校；分院管理员(role=2)仅限本学院，实现数据隔离。
 */
const auditLogController = {
  // 分院管理员强制注入本院过滤；院校管理员不限制
  _scopeCollege(req) {
    return req.user.role === 2 ? req.user.collegeId : null;
  },

  async list(req, res) {
    try {
      const filters = {
        keyword: req.query.keyword,
        userId: req.query.userId,
        action: req.query.action,
        success: req.query.success,
        startDate: req.query.startDate,
        endDate: req.query.endDate
      };
      const scoped = auditLogController._scopeCollege(req);
      if (scoped) filters.collegeId = scoped;
      const result = await auditLogModel.query(filters, clampPagination(req.query));
      return success(res, result, '获取审计日志成功');
    } catch (err) {
      return error(res, '获取审计日志失败：' + err.message, 500);
    }
  },

  async overview(req, res) {
    try {
      const days = Math.min(Number(req.query.days) || 7, 90);
      const scoped = auditLogController._scopeCollege(req);
      const data = await auditLogModel.overview(days, scoped);
      return success(res, data, '获取审计概览成功');
    } catch (err) {
      return error(res, '获取审计概览失败：' + err.message, 500);
    }
  }
};

module.exports = auditLogController;
