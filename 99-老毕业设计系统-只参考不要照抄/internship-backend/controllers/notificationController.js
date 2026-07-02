const { notificationModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const notificationController = {
  async list(req, res) {
    try {
      const result = await notificationModel.findByUser(req.user.id, clampPagination(req.query));
      return success(res, result, '获取通知成功');
    } catch (err) {
      return error(res, '获取通知失败：' + err.message, 500);
    }
  },

  async unreadCount(req, res) {
    try {
      const cnt = await notificationModel.unreadCount(req.user.id);
      return success(res, { count: cnt }, '获取未读数成功');
    } catch (err) {
      return error(res, '获取未读数失败：' + err.message, 500);
    }
  },

  async markRead(req, res) {
    try {
      await notificationModel.markRead(Number(req.params.id), req.user.id);
      return success(res, null, '已标记已读');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  async markAllRead(req, res) {
    try {
      await notificationModel.markAllRead(req.user.id);
      return success(res, null, '已全部标记已读');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  }
};

module.exports = notificationController;
