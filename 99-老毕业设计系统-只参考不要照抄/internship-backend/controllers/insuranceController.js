const { insuranceModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { runInsuranceScan } = require('../utils/scheduler');

const insuranceController = {
  async list(req, res) {
    try {
      const { student_id, keyword } = req.query;
      const user = req.user;
      const filter = { keyword, studentId: student_id !== undefined ? Number(student_id) : undefined };
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 4) filter.studentId = user.id; // 学生看自己的保险单

      const result = await insuranceModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取保险单列表成功');
    } catch (err) {
      return error(res, '获取保险单列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await insuranceModel.findById(Number(req.params.id));
      if (!item) return error(res, '保险单不存在', 404);
      const user = req.user;
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && item.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取保险单详情成功');
    } catch (err) {
      return error(res, '获取保险单详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { student_id } = req.body;
      if (!student_id) return error(res, '请指定学生', 400);
      const student = await userModel.findById(Number(student_id));
      if (!student || student.role !== 4) return error(res, '学生无效', 400);
      if (req.user.role === 2 && student.college_id !== req.user.collegeId) {
        return error(res, '只能为本学院学生录入保险单', 403);
      }
      const id = await insuranceModel.create({ ...req.body, student_id: Number(student_id), college_id: student.college_id });
      const item = await insuranceModel.findById(id);
      return success(res, item, '录入保险单成功', 201);
    } catch (err) {
      return error(res, '录入保险单失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await insuranceModel.findById(id);
      if (!item) return error(res, '保险单不存在', 404);
      if (req.user.role === 2 && item.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      await insuranceModel.update(id, req.body);
      const updated = await insuranceModel.findById(id);
      return success(res, updated, '更新保险单成功');
    } catch (err) {
      return error(res, '更新保险单失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await insuranceModel.findById(id);
      if (!item) return error(res, '保险单不存在', 404);
      if (req.user.role === 2 && item.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      await insuranceModel.remove(id);
      return success(res, null, '删除保险单成功');
    } catch (err) {
      return error(res, '删除保险单失败：' + err.message, 500);
    }
  },

  // 保险预警清单（只读，不发通知）：即将到期 + 未投保学生
  async warnings(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId : null;
      const days = Math.min(Number(req.query.days) || 15, 90);
      const [expiring, uninsured] = await Promise.all([
        insuranceModel.findExpiringSoon(days),
        insuranceModel.findUninsuredInterns(collegeId)
      ]);
      return success(res, { expiring, uninsured, days }, '获取保险预警成功');
    } catch (err) {
      return error(res, '获取保险预警失败：' + err.message, 500);
    }
  },

  // 手动触发保险扫描并发送预警通知（管理员/演示用）
  async scan(req, res) {
    try {
      const result = await runInsuranceScan();
      return success(res, result, `扫描完成：到期 ${result.expiring} 条，未投保 ${result.uninsured} 人`);
    } catch (err) {
      return error(res, '扫描失败：' + err.message, 500);
    }
  }
};

module.exports = insuranceController;
