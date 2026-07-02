const { internPlanModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

// status: 1申报 2通过 3开启 4结束 5驳回
const internPlanController = {
  async list(req, res) {
    try {
      const { status, college_id } = req.query;
      const user = req.user;
      const filter = { status: status !== undefined ? Number(status) : undefined };

      if (user.role === 1) {
        if (college_id !== undefined) filter.collegeId = Number(college_id);
      } else if (user.role === 2) {
        filter.collegeId = user.collegeId;
      } else {
        // 指导教师/学生：仅本学院、已开启或已结束的计划
        filter.collegeId = user.collegeId;
        filter.openedOnly = true;
      }

      const result = await internPlanModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取实习计划列表成功');
    } catch (err) {
      return error(res, '获取实习计划列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const plan = await internPlanModel.findById(Number(req.params.id));
      if (!plan) return error(res, '实习计划不存在', 404);
      if (req.user.role === 2 && plan.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      return success(res, plan, '获取实习计划详情成功');
    } catch (err) {
      return error(res, '获取实习计划详情失败：' + err.message, 500);
    }
  },

  // 分院/院校制定计划（状态：申报）
  async create(req, res) {
    try {
      const body = req.body;
      if (!body.title) return error(res, '计划标题不能为空', 400);

      // 分院管理员强制归属本学院；院校管理员需显式指定 college_id
      let collegeId = body.college_id;
      if (req.user.role === 2) collegeId = req.user.collegeId;
      if (!collegeId) return error(res, '请指定所属分院', 400);

      const id = await internPlanModel.create({
        ...body,
        college_id: Number(collegeId),
        created_by: req.user.id
      });
      const plan = await internPlanModel.findById(id);
      return success(res, plan, '实习计划已创建（待审批）', 201);
    } catch (err) {
      return error(res, '创建实习计划失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const plan = await internPlanModel.findById(id);
      if (!plan) return error(res, '实习计划不存在', 404);
      if (req.user.role === 2 && plan.college_id !== req.user.collegeId) {
        return error(res, '权限不足，只能修改本学院的计划', 403);
      }
      if (![1, 5].includes(plan.status)) {
        return error(res, '只有“申报中”或“被驳回”的计划可以修改', 400);
      }
      await internPlanModel.update(id, req.body);
      const updated = await internPlanModel.findById(id);
      return success(res, updated, '实习计划已更新');
    } catch (err) {
      return error(res, '更新实习计划失败：' + err.message, 500);
    }
  },

  // 院校审批（通过/驳回）
  async approve(req, res) {
    try {
      const id = Number(req.params.id);
      const plan = await internPlanModel.findById(id);
      if (!plan) return error(res, '实习计划不存在', 404);
      if (plan.status !== 1) return error(res, '该计划不在待审批状态', 400);

      const { agree, reason } = req.body;
      if (agree === undefined) return error(res, '请指定审批结果', 400);
      if (!agree && !reason) return error(res, '驳回时请填写原因', 400);

      await internPlanModel.updateStatus(id, agree ? 2 : 5, agree ? null : reason);
      const updated = await internPlanModel.findById(id);
      await notify(plan.created_by, '实习计划审批结果',
        `实习计划「${plan.title}」${agree ? '已通过审批，可开启' : '被驳回'}${!agree && reason ? '：' + reason : ''}`,
        agree ? 'success' : 'warning');
      return success(res, updated, agree ? '审批通过' : '已驳回');
    } catch (err) {
      return error(res, '审批失败：' + err.message, 500);
    }
  },

  // 分院开启计划（通过后手动开启）
  async open(req, res) {
    try {
      const id = Number(req.params.id);
      const plan = await internPlanModel.findById(id);
      if (!plan) return error(res, '实习计划不存在', 404);
      if (req.user.role === 2 && plan.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      if (plan.status !== 2) return error(res, '只有“审批通过”的计划可以开启', 400);
      await internPlanModel.updateStatus(id, 3);
      const updated = await internPlanModel.findById(id);
      return success(res, updated, '实习计划已开启');
    } catch (err) {
      return error(res, '开启实习计划失败：' + err.message, 500);
    }
  },

  // 关闭/结束计划
  async close(req, res) {
    try {
      const id = Number(req.params.id);
      const plan = await internPlanModel.findById(id);
      if (!plan) return error(res, '实习计划不存在', 404);
      if (req.user.role === 2 && plan.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      if (plan.status !== 3) return error(res, '只有“已开启”的计划可以结束', 400);
      await internPlanModel.updateStatus(id, 4);
      const updated = await internPlanModel.findById(id);
      return success(res, updated, '实习计划已结束');
    } catch (err) {
      return error(res, '结束实习计划失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const plan = await internPlanModel.findById(id);
      if (!plan) return error(res, '实习计划不存在', 404);
      if (req.user.role === 2 && plan.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      if (![1, 5].includes(plan.status)) {
        return error(res, '只有“申报中”或“被驳回”的计划可以删除', 400);
      }
      await internPlanModel.remove(id);
      return success(res, null, '实习计划已删除');
    } catch (err) {
      return error(res, '删除实习计划失败：' + err.message, 500);
    }
  }
};

module.exports = internPlanController;
