const { classModel, majorModel, collegeModel } = require('../models');
const { success, error } = require('../utils/response');

const classController = {
  async list(req, res) {
    try {
      const { college_id, major_id, grade, status, keyword } = req.query;
      const list = await classModel.findAll({
        collegeId: college_id !== undefined ? Number(college_id) : undefined,
        majorId:   major_id   !== undefined ? Number(major_id)   : undefined,
        grade:     grade      !== undefined ? Number(grade)      : undefined,
        status:    status     !== undefined ? Number(status)     : undefined,
        keyword
      });
      return success(res, list, '获取班级列表成功');
    } catch (err) {
      return error(res, '获取班级列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const cls = await classModel.findById(Number(req.params.id));
      if (!cls) return error(res, '班级不存在', 404);
      return success(res, cls, '获取班级详情成功');
    } catch (err) {
      return error(res, '获取班级详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { major_id, name, grade, status } = req.body;
      if (!major_id || !name || !grade) return error(res, '所属专业、班级名称和年级不能为空', 400);

      const major = await majorModel.findById(Number(major_id));
      if (!major) return error(res, '所属专业不存在', 404);

      const id = await classModel.create({
        major_id:   Number(major_id),
        college_id: major.college_id,
        name,
        grade:  Number(grade),
        status
      });
      const cls = await classModel.findById(id);
      return success(res, cls, '创建班级成功', 201);
    } catch (err) {
      return error(res, '创建班级失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const cls = await classModel.findById(id);
      if (!cls) return error(res, '班级不存在', 404);

      const { major_id, name, grade, status } = req.body;
      let college_id;
      if (major_id) {
        const major = await majorModel.findById(Number(major_id));
        if (!major) return error(res, '所属专业不存在', 404);
        college_id = major.college_id;
      }

      await classModel.update(id, {
        major_id:   major_id !== undefined ? Number(major_id) : undefined,
        college_id,
        name,
        grade:  grade !== undefined ? Number(grade) : undefined,
        status
      });
      const updated = await classModel.findById(id);
      return success(res, updated, '更新班级成功');
    } catch (err) {
      return error(res, '更新班级失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const cls = await classModel.findById(id);
      if (!cls) return error(res, '班级不存在', 404);
      await classModel.remove(id);
      return success(res, null, '删除班级成功');
    } catch (err) {
      return error(res, '删除班级失败：' + err.message, 500);
    }
  }
};

module.exports = classController;
