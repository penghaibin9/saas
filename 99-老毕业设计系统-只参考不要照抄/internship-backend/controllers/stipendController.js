const stipendModel = require('../models/stipendModel');
const stipendService = require('../services/stipendService');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { AppError } = require('../utils/errors');

const METHODS = ['bank', 'cash', 'wechat', 'alipay'];
const PERIOD_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

function canManage(role) { return [1, 2, 3].includes(role); }

const stipendController = {
  // 列表：学生看本人；教师/管理员看分管范围
  async list(req, res) {
    try {
      const u = req.user;
      const filter = {
        period: req.query.period,
        status: req.query.status !== undefined ? Number(req.query.status) : undefined,
        keyword: req.query.keyword,
      };
      if (u.role === 4) filter.studentId = u.id;
      else if (u.role === 2) filter.collegeId = u.collegeId;
      else if (u.role === 5) return error(res, '企业端无权查看报酬台账', 403);
      const result = await stipendModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取实习报酬台账成功');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  async detail(req, res) {
    try {
      const row = await stipendModel.findById(Number(req.params.id));
      if (!row) return error(res, '记录不存在', 404);
      const u = req.user;
      if (u.role === 4 && row.student_id !== u.id) return error(res, '权限不足', 403);
      if (u.role === 2 && row.college_id !== u.collegeId) return error(res, '权限不足', 403);
      row.compliant = stipendModel.compliant(row.amount, row.base_salary_ref);
      return success(res, row, '获取详情成功');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  // 入参由 validate(stipendCreate) 前置校验；此处仅角色判断 + 调 service（业务/合规在 service）
  async create(req, res, next) {
    try {
      if (!canManage(req.user.role)) throw AppError.forbidden('仅教师/管理员可登记报酬');
      const row = await stipendService.create(req.body, req.user.id);
      return success(res, row, '已登记', 201);
    } catch (e) { next(e); }
  },

  async update(req, res) {
    try {
      if (!canManage(req.user.role)) return error(res, '权限不足', 403);
      const row = await stipendModel.findById(Number(req.params.id));
      if (!row) return error(res, '记录不存在', 404);
      if (req.user.role === 2 && row.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      if (req.body.period && !PERIOD_RE.test(req.body.period)) return error(res, '发放周期格式应为 YYYY-MM', 400);
      if (req.body.method && !METHODS.includes(req.body.method)) return error(res, '发放方式不合法', 400);
      if (req.body.status !== undefined && ![0, 1, 2].includes(Number(req.body.status))) return error(res, '状态不合法', 400);
      await stipendModel.update(Number(req.params.id), req.body);
      const updated = await stipendModel.findById(Number(req.params.id));
      updated.compliant = stipendModel.compliant(updated.amount, updated.base_salary_ref);
      return success(res, updated, '已更新');
    } catch (e) { return error(res, '更新失败：' + e.message, 500); }
  },

  async remove(req, res) {
    try {
      if (![1, 2].includes(req.user.role)) return error(res, '仅管理员可删除', 403);
      const row = await stipendModel.findById(Number(req.params.id));
      if (!row) return error(res, '记录不存在', 404);
      if (req.user.role === 2 && row.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      await stipendModel.remove(Number(req.params.id));
      return success(res, null, '已删除');
    } catch (e) { return error(res, '删除失败：' + e.message, 500); }
  },

  // 发放进度 + 合规率统计
  async stats(req, res) {
    try {
      if (!canManage(req.user.role)) return error(res, '权限不足', 403);
      const filter = { period: req.query.period };
      if (req.user.role === 2) filter.collegeId = req.user.collegeId;
      const s = await stipendModel.stats(filter);
      return success(res, s, '统计成功');
    } catch (e) { return error(res, '统计失败：' + e.message, 500); }
  },
};

module.exports = stipendController;
