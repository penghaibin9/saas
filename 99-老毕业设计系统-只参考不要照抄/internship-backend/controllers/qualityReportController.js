const { qualityReportModel } = require('../models');
const { success, error } = require('../utils/response');

const qualityReportController = {
  async generate(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId
        : (req.query.college_id ? Number(req.query.college_id) : undefined);
      const data = await qualityReportModel.generate({ collegeId });
      return success(res, data, '生成实习质量报告成功');
    } catch (err) {
      return error(res, '生成报告失败：' + err.message, 500);
    }
  }
};

module.exports = qualityReportController;
