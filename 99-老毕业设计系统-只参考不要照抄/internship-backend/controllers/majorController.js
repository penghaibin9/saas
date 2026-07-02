const { majorModel, collegeModel } = require('../models');
const { success, error } = require('../utils/response');

const majorController = {
  async list(req, res) {
    try {
      const { college_id, status, keyword } = req.query;
      const list = await majorModel.findAll({
        collegeId: college_id !== undefined ? Number(college_id) : undefined,
        status:    status    !== undefined ? Number(status)    : undefined,
        keyword
      });
      return success(res, list, '获取专业列表成功');
    } catch (err) {
      return error(res, '获取专业列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const major = await majorModel.findById(Number(req.params.id));
      if (!major) return error(res, '专业不存在', 404);
      return success(res, major, '获取专业详情成功');
    } catch (err) {
      return error(res, '获取专业详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { college_id, name, code, description, status } = req.body;
      if (!college_id || !name || !code) return error(res, '所属学院、专业名称和编码不能为空', 400);

      const college = await collegeModel.findById(Number(college_id));
      if (!college) return error(res, '所属学院不存在', 404);

      const existing = await majorModel.findByCode(code);
      if (existing) return error(res, '专业编码已存在', 409);

      const id = await majorModel.create({ college_id: Number(college_id), name, code, description, status });
      const major = await majorModel.findById(id);
      return success(res, major, '创建专业成功', 201);
    } catch (err) {
      return error(res, '创建专业失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const major = await majorModel.findById(id);
      if (!major) return error(res, '专业不存在', 404);

      const { college_id, name, code, description, status } = req.body;
      if (code && code !== major.code) {
        const dup = await majorModel.findByCode(code);
        if (dup) return error(res, '专业编码已存在', 409);
      }
      if (college_id) {
        const college = await collegeModel.findById(Number(college_id));
        if (!college) return error(res, '所属学院不存在', 404);
      }

      await majorModel.update(id, {
        college_id: college_id !== undefined ? Number(college_id) : undefined,
        name, code, description, status
      });
      const updated = await majorModel.findById(id);
      return success(res, updated, '更新专业成功');
    } catch (err) {
      return error(res, '更新专业失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const major = await majorModel.findById(id);
      if (!major) return error(res, '专业不存在', 404);
      await majorModel.remove(id);
      return success(res, null, '删除专业成功');
    } catch (err) {
      return error(res, '删除专业失败：' + err.message, 500);
    }
  }
};

module.exports = majorController;
