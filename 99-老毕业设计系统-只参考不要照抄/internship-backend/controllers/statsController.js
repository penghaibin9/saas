const { statsModel } = require('../models');
const { success, error } = require('../utils/response');

const statsController = {
  async overview(req, res) {
    try {
      const { role, id: userId, collegeId } = req.user;
      let data;
      if (role === 1) data = await statsModel.adminOverview(null);
      else if (role === 2) data = await statsModel.adminOverview(collegeId);
      else if (role === 3) data = await statsModel.teacherOverview(userId);
      else data = await statsModel.studentOverview(userId);
      return success(res, data, '获取统计数据成功');
    } catch (err) {
      return error(res, '获取统计数据失败：' + err.message, 500);
    }
  }
};

module.exports = statsController;
