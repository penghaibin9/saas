const path = require('path');
const fs = require('fs');
const { reportModel, applicationModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl, UPLOADS_DIR } = require('../utils/upload');

const ALLOWED_EXT = ['.pdf', '.doc', '.docx', '.zip'];

// 经对象存储抽象层的报告上传器（随机文件名 + 扩展名白名单；local/oss/s3 自动适配）
const upload = createUploader({ prefix: 'report', allowedExt: ALLOWED_EXT });

const reportController = {
  upload: upload.single('file'),

  async list(req, res) {
    try {
      const { application_id, status } = req.query;
      const user = req.user;

      const filter = {
        applicationId: application_id !== undefined ? Number(application_id) : undefined,
        status:        status         !== undefined ? Number(status)         : undefined,
      };
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看全量报告（请用企业端）

      const result = await reportModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取报告列表成功');
    } catch (err) {
      return error(res, '获取报告列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const report = await reportModel.findById(Number(req.params.id));
      if (!report) return error(res, '报告不存在', 404);

      const user = req.user;
      if (user.role === 4 && report.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && report.teacher_id !== user.id) return error(res, '权限不足', 403);

      return success(res, report, '获取报告详情成功');
    } catch (err) {
      return error(res, '获取报告详情失败：' + err.message, 500);
    }
  },

  // 学生创建草稿
  async create(req, res) {
    try {
      const { application_id, title, content } = req.body;
      if (!application_id || !title) return error(res, '申请ID和报告标题不能为空', 400);

      const application = await applicationModel.findById(Number(application_id));
      if (!application) return error(res, '申请不存在', 404);
      if (application.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (application.status !== 3 && application.status !== 5) {
        return error(res, '申请尚未通过审核，不能提交报告', 400);
      }

      const existing = await reportModel.findByApplication(Number(application_id));
      if (existing) return error(res, '该申请已有实习报告', 409);

      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await reportModel.create({
        application_id: Number(application_id),
        student_id: req.user.id,
        title, content, file_url
      });
      const report = await reportModel.findById(id);
      return success(res, report, '报告草稿创建成功', 201);
    } catch (err) {
      return error(res, '创建报告失败：' + err.message, 500);
    }
  },

  // 学生更新草稿
  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const report = await reportModel.findById(id);
      if (!report) return error(res, '报告不存在', 404);
      if (report.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (report.status !== 0) return error(res, '已提交的报告不能修改', 400);

      const { title, content } = req.body;
      const file_url = req.file ? keyToUrl(req.file.filename) : undefined;
      await reportModel.updateDraft(id, { title, content, file_url });
      const updated = await reportModel.findById(id);
      return success(res, updated, '报告更新成功');
    } catch (err) {
      return error(res, '更新报告失败：' + err.message, 500);
    }
  },

  // 学生提交报告
  async submit(req, res) {
    try {
      const id = Number(req.params.id);
      const report = await reportModel.findById(id);
      if (!report) return error(res, '报告不存在', 404);
      if (report.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (report.status !== 0) return error(res, '报告已提交', 400);

      await reportModel.submit(id);
      const updated = await reportModel.findById(id);
      return success(res, updated, '报告提交成功');
    } catch (err) {
      return error(res, '提交报告失败：' + err.message, 500);
    }
  },

  // 教师评阅
  async review(req, res) {
    try {
      const id = Number(req.params.id);
      const report = await reportModel.findById(id);
      if (!report) return error(res, '报告不存在', 404);
      if (report.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      if (report.status !== 1) return error(res, '报告未提交或已评阅', 400);

      const { teacher_score, teacher_comment } = req.body;
      if (teacher_score === undefined) return error(res, '请给出评分', 400);
      const score = Number(teacher_score);
      if (score < 0 || score > 100) return error(res, '评分需在 0-100 之间', 400);

      await reportModel.review(id, { teacher_score: score, teacher_comment });
      const updated = await reportModel.findById(id);
      return success(res, updated, '评阅完成');
    } catch (err) {
      return error(res, '评阅失败：' + err.message, 500);
    }
  },

  // 鉴权下载报告附件（替代直接访问 /uploads 静态路径，避免越权与枚举）
  async download(req, res) {
    try {
      const report = await reportModel.findById(Number(req.params.id));
      if (!report) return error(res, '报告不存在', 404);

      const user = req.user;
      if (user.role === 4 && report.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && report.teacher_id !== user.id) return error(res, '权限不足', 403);

      if (!report.file_url) return error(res, '该报告没有附件', 404);

      // 仅取文件名，杜绝 ../ 路径穿越；并确保解析后仍在 uploads 目录内
      const fileName = path.basename(report.file_url);
      const filePath = path.join(UPLOADS_DIR, fileName);
      if (path.dirname(filePath) !== UPLOADS_DIR || !fs.existsSync(filePath)) {
        return error(res, '附件文件不存在', 404);
      }

      return res.download(filePath, fileName);
    } catch (err) {
      return error(res, '下载失败：' + err.message, 500);
    }
  }
};

module.exports = reportController;
