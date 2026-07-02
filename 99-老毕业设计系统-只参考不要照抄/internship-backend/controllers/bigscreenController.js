const bigscreenModel = require('../models/bigscreenModel');
const { success, error } = require('../utils/response');

// 监管大屏（院校/分院管理员 + 指导教师可看；分院仅本院数据）
function scope(req) {
  return req.user.role === 2 ? { collegeId: req.user.collegeId } : {};
}
function canView(role) { return [1, 2, 3].includes(role); }

const bigscreenController = {
  // GIS 实习分布（地图点位 + 学院汇总）
  async gis(req, res) {
    try {
      if (!canView(req.user.role)) return error(res, '权限不足', 403);
      const points = await bigscreenModel.gisPoints(scope(req));
      const byCollege = await bigscreenModel.byCollege();
      return success(res, { points, byCollege, totalEnterprises: points.length }, 'GIS 分布');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  // 多维风险雷达
  async riskRadar(req, res) {
    try {
      if (!canView(req.user.role)) return error(res, '权限不足', 403);
      const dims = await bigscreenModel.riskRadar(scope(req));
      const total = dims.reduce((s, d) => s + d.value, 0);
      return success(res, { dimensions: dims, total, generatedAt: new Date().toISOString() }, '风险雷达');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },
};

module.exports = bigscreenController;
