const { gdGuidanceModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

const gdGuidanceController = {
  async list(req, res) {
    try {
      const { student_id, topic_id } = req.query;
      const user = req.user;
      const filter = {
        studentId: student_id !== undefined ? Number(student_id) : undefined,
        topicId:   topic_id   !== undefined ? Number(topic_id)   : undefined,
      };
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看毕设指导记录

      const result = await gdGuidanceModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取指导记录成功');
    } catch (err) {
      return error(res, '获取指导记录失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await gdGuidanceModel.findById(Number(req.params.id));
      if (!item) return error(res, '指导记录不存在', 404);
      const user = req.user;
      if (user.role === 3 && item.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      return success(res, item, '获取指导记录详情成功');
    } catch (err) {
      return error(res, '获取指导记录详情失败：' + err.message, 500);
    }
  },

  // 教师创建指导记录
  async create(req, res) {
    try {
      const { student_id, title, content, guidance_date, topic_id } = req.body;
      if (!student_id) return error(res, '请指定学生', 400);
      const student = await userModel.findById(Number(student_id));
      if (!student || student.role !== 4) return error(res, '学生无效', 400);

      const id = await gdGuidanceModel.create({
        student_id: Number(student_id), teacher_id: req.user.id, college_id: student.college_id,
        title, content, guidance_date, topic_id: topic_id ? Number(topic_id) : null
      });
      await notify(Number(student_id), '新的毕业设计指导记录',
        `指导老师新增了一条指导记录${title ? '：' + title : ''}`, 'info');
      const item = await gdGuidanceModel.findById(id);
      return success(res, item, '指导记录已保存', 201);
    } catch (err) {
      return error(res, '保存指导记录失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdGuidanceModel.findById(id);
      if (!item) return error(res, '指导记录不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '只能修改自己的指导记录', 403);
      await gdGuidanceModel.update(id, req.body);
      const updated = await gdGuidanceModel.findById(id);
      return success(res, updated, '更新指导记录成功');
    } catch (err) {
      return error(res, '更新指导记录失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdGuidanceModel.findById(id);
      if (!item) return error(res, '指导记录不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '只能删除自己的指导记录', 403);
      await gdGuidanceModel.remove(id);
      return success(res, null, '删除指导记录成功');
    } catch (err) {
      return error(res, '删除指导记录失败：' + err.message, 500);
    }
  }
};

module.exports = gdGuidanceController;
