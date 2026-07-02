const { internStatsModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const internStatsController = {
  // 未打卡学生（默认1天，可自定义天数）
  async uncheckedStudents(req, res) {
    try {
      let days = Number(req.query.days);
      if (!Number.isFinite(days) || days < 1) days = 1;
      days = Math.min(Math.floor(days), 90);
      const list = await internStatsModel.uncheckedStudents(req.user, days);
      return success(res, { days, total: list.length, list }, '获取未打卡学生成功');
    } catch (err) {
      return error(res, '获取未打卡学生失败：' + err.message, 500);
    }
  },

  // 实习过程统计（每学生签到/周报/月报完成情况）
  async process(req, res) {
    try {
      const keyword = String(req.query.keyword || req.query.q || '').trim();
      const result = await internStatsModel.processStats(req.user, {
        ...clampPagination(req.query),
        keyword: keyword || undefined
      });
      return success(res, result, '获取实习过程统计成功');
    } catch (err) {
      return error(res, '获取实习过程统计失败：' + err.message, 500);
    }
  },

  // 未达标学生（签到/周报/月报未满足计划要求）
  async incomplete(req, res) {
    try {
      const result = await internStatsModel.incompleteStudents(req.user, clampPagination(req.query));
      return success(res, result, '获取未达标学生成功');
    } catch (err) {
      return error(res, '获取未达标学生失败：' + err.message, 500);
    }
  },

  // 汇总卡片
  async summary(req, res) {
    try {
      const data = await internStatsModel.summary(req.user);
      return success(res, data, '获取实习统计概览成功');
    } catch (err) {
      return error(res, '获取实习统计概览失败：' + err.message, 500);
    }
  }
};

module.exports = internStatsController;
