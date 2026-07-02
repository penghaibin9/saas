const { gdTaskModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

// 毕业设计任务时间节点：院校管理员维护，所有角色可查看“各环节完成情况”
const gdTaskController = {
  async list(req, res) {
    try {
      const { status, parent_id, only_root } = req.query;
      const user = req.user;
      const filter = {
        status: status !== undefined ? Number(status) : undefined,
        parentId: parent_id !== undefined ? Number(parent_id) : undefined,
        onlyRoot: only_root === '1' || only_root === 'true',
      };
      // 非院校管理员仅看本学院或全校任务
      if (user.role !== 1) filter.collegeId = user.collegeId;

      const result = await gdTaskModel.findAll(filter, clampPagination(req.query, { defaultPageSize: 50, maxPageSize: 200 }));
      return success(res, result, '获取任务节点成功');
    } catch (err) {
      return error(res, '获取任务节点失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await gdTaskModel.findById(Number(req.params.id));
      if (!item) return error(res, '任务不存在', 404);
      return success(res, item, '获取任务详情成功');
    } catch (err) {
      return error(res, '获取任务详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { name } = req.body;
      if (!name) return error(res, '任务名称不能为空', 400);
      let college_id = req.body.college_id;
      if (req.user.role === 2) college_id = req.user.collegeId;
      const id = await gdTaskModel.create({ ...req.body, college_id: college_id ? Number(college_id) : null });
      const item = await gdTaskModel.findById(id);
      return success(res, item, '创建任务成功', 201);
    } catch (err) {
      return error(res, '创建任务失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTaskModel.findById(id);
      if (!item) return error(res, '任务不存在', 404);
      if (req.user.role === 2 && item.college_id && item.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      const fields = { ...req.body };
      if (req.user.role === 2) delete fields.college_id;
      await gdTaskModel.update(id, fields);
      const updated = await gdTaskModel.findById(id);
      return success(res, updated, '更新任务成功');
    } catch (err) {
      return error(res, '更新任务失败：' + err.message, 500);
    }
  },

  // 标记完成（自动写实际完成时间）
  async complete(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTaskModel.findById(id);
      if (!item) return error(res, '任务不存在', 404);
      const actual = req.body.actual_time || new Date().toISOString().slice(0, 10);
      await gdTaskModel.update(id, { status: 2, actual_time: actual, description: req.body.description });
      const updated = await gdTaskModel.findById(id);
      return success(res, updated, '任务已标记完成');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdTaskModel.findById(id);
      if (!item) return error(res, '任务不存在', 404);
      if (req.user.role === 2 && item.college_id && item.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      await gdTaskModel.remove(id);
      return success(res, null, '删除任务成功（含子任务）');
    } catch (err) {
      return error(res, '删除任务失败：' + err.message, 500);
    }
  }
};

module.exports = gdTaskController;
