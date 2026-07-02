const { announcementModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl } = require('../utils/upload');

const upload = createUploader({ prefix: 'notice' });

const announcementController = {
  upload: upload.single('file'),

  async list(req, res) {
    try {
      const { category, status, keyword, college_id } = req.query;
      const user = req.user;
      const filter = { category, keyword };

      // 管理员可看草稿与全部；教师/学生只看已发布且对其可见
      if (user.role === 1) {
        if (college_id !== undefined) filter.collegeId = Number(college_id);
        if (status !== undefined) filter.status = Number(status);
      } else if (user.role === 2) {
        filter.visibleCollegeId = user.collegeId;
        if (status !== undefined) filter.status = Number(status);
      } else {
        filter.visibleCollegeId = user.collegeId;
        filter.status = 1;
      }

      const result = await announcementModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取公示信息成功');
    } catch (err) {
      return error(res, '获取公示信息失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await announcementModel.findById(Number(req.params.id));
      if (!item) return error(res, '公示信息不存在', 404);
      // 非管理员只能看已发布且可见的
      if (![1, 2].includes(req.user.role)) {
        if (item.status !== 1) return error(res, '公示信息不存在', 404);
        if (item.college_id && item.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      }
      return success(res, item, '获取公示信息详情成功');
    } catch (err) {
      return error(res, '获取公示信息详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { title, category, content, status } = req.body;
      if (!title) return error(res, '标题不能为空', 400);

      // 分院管理员发布的公示归属本学院
      let college_id = req.body.college_id;
      if (req.user.role === 2) college_id = req.user.collegeId;

      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await announcementModel.create({
        title, category, content, file_url,
        college_id: college_id ? Number(college_id) : null,
        publisher_id: req.user.id,
        status: status !== undefined ? Number(status) : 1
      });
      const item = await announcementModel.findById(id);
      return success(res, item, '发布成功', 201);
    } catch (err) {
      return error(res, '发布失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await announcementModel.findById(id);
      if (!item) return error(res, '公示信息不存在', 404);
      if (req.user.role === 2 && item.college_id !== req.user.collegeId) {
        return error(res, '权限不足，只能管理本学院公示', 403);
      }
      const fields = { ...req.body };
      if (req.user.role === 2) delete fields.college_id; // 分院不可改归属
      if (req.file) fields.file_url = keyToUrl(req.file.filename);
      await announcementModel.update(id, fields);
      const updated = await announcementModel.findById(id);
      return success(res, updated, '更新成功');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await announcementModel.findById(id);
      if (!item) return error(res, '公示信息不存在', 404);
      if (req.user.role === 2 && item.college_id !== req.user.collegeId) {
        return error(res, '权限不足', 403);
      }
      await announcementModel.remove(id);
      return success(res, null, '删除成功');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = announcementController;
