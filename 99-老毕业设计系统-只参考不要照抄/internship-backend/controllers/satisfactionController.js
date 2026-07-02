const { satisfactionModel, enterpriseModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const satisfactionController = {
  async list(req, res) {
    try {
      const { enterprise_id, student_id } = req.query;
      const filter = {
        enterpriseId: enterprise_id !== undefined ? Number(enterprise_id) : undefined,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
      };
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const result = await satisfactionModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取满意度评价成功');
    } catch (err) {
      return error(res, '获取满意度评价失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { enterprise_id, student_id, score, content } = req.body;
      if (!enterprise_id) return error(res, '请指定企业', 400);
      const sc = Number(score);
      if (!Number.isInteger(sc) || sc < 1 || sc > 5) return error(res, '满意度评分需为 1-5 的整数', 400);
      const ent = await enterpriseModel.findById(Number(enterprise_id));
      if (!ent) return error(res, '企业不存在', 404);

      const id = await satisfactionModel.create({
        enterprise_id: Number(enterprise_id),
        student_id: student_id ? Number(student_id) : null,
        college_id: req.user.role === 2 ? req.user.collegeId : (req.body.college_id || null),
        score: sc, content, created_by: req.user.id
      });
      const item = await satisfactionModel.findById(id);
      return success(res, item, '评价已提交', 201);
    } catch (err) {
      return error(res, '提交评价失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await satisfactionModel.findById(id);
      if (!item) return error(res, '评价不存在', 404);
      await satisfactionModel.remove(id);
      return success(res, null, '删除成功');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  },

  // 满意度分析（概览 + 各企业平均）
  async analytics(req, res) {
    try {
      const collegeId = req.user.role === 2 ? req.user.collegeId : undefined;
      const overall = await satisfactionModel.overall(collegeId);
      const byEnterprise = await satisfactionModel.byEnterprise(collegeId);
      return success(res, { overall, byEnterprise }, '获取满意度分析成功');
    } catch (err) {
      return error(res, '获取满意度分析失败：' + err.message, 500);
    }
  }
};

module.exports = satisfactionController;
