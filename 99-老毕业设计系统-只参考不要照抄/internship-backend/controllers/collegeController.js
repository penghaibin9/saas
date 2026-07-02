const { collegeModel } = require('../models');
const { success, error } = require('../utils/response');

const collegeController = {
  async list(req, res) {
    try {
      const { status, keyword } = req.query;
      const statusNum = status !== undefined ? Number(status) : undefined;
      const list = await collegeModel.findAll({ status: statusNum, keyword });
      return success(res, list, '获取学院列表成功');
    } catch (err) {
      return error(res, '获取学院列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const college = await collegeModel.findById(Number(req.params.id));
      if (!college) return error(res, '学院不存在', 404);
      return success(res, college, '获取学院详情成功');
    } catch (err) {
      return error(res, '获取学院详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { name, code, description, status } = req.body;
      if (!name || !code) return error(res, '学院名称和编码不能为空', 400);

      const existing = await collegeModel.findByCode(code);
      if (existing) return error(res, '学院编码已存在', 409);

      const id = await collegeModel.create({ name, code, description, status });
      const college = await collegeModel.findById(id);
      return success(res, college, '创建学院成功', 201);
    } catch (err) {
      return error(res, '创建学院失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const college = await collegeModel.findById(id);
      if (!college) return error(res, '学院不存在', 404);

      const { name, code, description, status } = req.body;
      if (code && code !== college.code) {
        const dup = await collegeModel.findByCode(code);
        if (dup) return error(res, '学院编码已存在', 409);
      }

      await collegeModel.update(id, { name, code, description, status });
      const updated = await collegeModel.findById(id);
      return success(res, updated, '更新学院成功');
    } catch (err) {
      return error(res, '更新学院失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const college = await collegeModel.findById(id);
      if (!college) return error(res, '学院不存在', 404);
      await collegeModel.remove(id);
      return success(res, null, '删除学院成功');
    } catch (err) {
      return error(res, '删除学院失败：' + err.message, 500);
    }
  }
};

module.exports = collegeController;
