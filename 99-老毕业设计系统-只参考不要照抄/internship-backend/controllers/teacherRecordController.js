const { teacherRecordModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl } = require('../utils/upload');

const upload = createUploader({ prefix: 'trec' });
const VALID_TYPES = ['monthly', 'visit'];

const teacherRecordController = {
  upload: upload.single('file'),

  async list(req, res) {
    try {
      const { type, status } = req.query;
      const user = req.user;
      const filter = {
        type: type !== undefined ? type : undefined,
        status: status !== undefined ? Number(status) : undefined,
      };
      if (user.role === 3) filter.teacherId = user.id;       // 教师看自己的
      else if (user.role === 2) filter.collegeId = user.collegeId; // 分院看本院教师的
      // 院校管理员看全部

      const result = await teacherRecordModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取教师记录成功');
    } catch (err) {
      return error(res, '获取教师记录失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await teacherRecordModel.findById(Number(req.params.id));
      if (!item) return error(res, '记录不存在', 404);
      if (req.user.role === 3 && item.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      if (req.user.role === 2 && item.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取记录详情成功');
    } catch (err) {
      return error(res, '获取记录详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { type = 'monthly', title } = req.body;
      if (!VALID_TYPES.includes(type)) return error(res, '类型仅支持 monthly/visit', 400);
      if (!title) return error(res, '标题不能为空', 400);
      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await teacherRecordModel.create({
        ...req.body, type, teacher_id: req.user.id, college_id: req.user.collegeId, file_url
      });
      const item = await teacherRecordModel.findById(id);
      return success(res, item, '已保存', 201);
    } catch (err) {
      return error(res, '保存失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await teacherRecordModel.findById(id);
      if (!item) return error(res, '记录不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      if (item.status !== 0) return error(res, '已提交的记录不可修改', 400);
      const fields = { ...req.body };
      if (req.file) fields.file_url = keyToUrl(req.file.filename);
      await teacherRecordModel.update(id, fields);
      const updated = await teacherRecordModel.findById(id);
      return success(res, updated, '更新成功');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  },

  async submit(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await teacherRecordModel.findById(id);
      if (!item) return error(res, '记录不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      await teacherRecordModel.submit(id);
      const updated = await teacherRecordModel.findById(id);
      return success(res, updated, '已提交');
    } catch (err) {
      return error(res, '提交失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await teacherRecordModel.findById(id);
      if (!item) return error(res, '记录不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      await teacherRecordModel.remove(id);
      return success(res, null, '删除成功');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = teacherRecordController;
