const { internLogModel, assignmentModel, systemConfigModel } = require('../models');

const DEFAULT_TPL = {
  weekly: '一、本周实习内容：\n\n二、收获与体会：\n\n三、遇到的问题：\n\n四、下周计划：',
  monthly: '一、本月实习概况：\n\n二、主要工作与成果：\n\n三、能力提升：\n\n四、存在问题与改进：\n\n五、下月计划：'
};
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl } = require('../utils/upload');
const { notify } = require('../utils/notify');

const upload = createUploader({ prefix: 'log' });
const VALID_TYPES = ['weekly', 'monthly'];

const internLogController = {
  upload: upload.single('file'),

  async list(req, res) {
    try {
      const { type, status, student_id } = req.query;
      const user = req.user;
      const filter = {
        type:   type   !== undefined ? type : undefined,
        status: status !== undefined ? Number(status) : undefined,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
      };
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看全量日志（请用企业端）

      const result = await internLogModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取周报/月报列表成功');
    } catch (err) {
      return error(res, '获取列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const log = await internLogModel.findById(Number(req.params.id));
      if (!log) return error(res, '记录不存在', 404);
      const user = req.user;
      if (user.role === 4 && log.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && log.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && log.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, log, '获取详情成功');
    } catch (err) {
      return error(res, '获取详情失败：' + err.message, 500);
    }
  },

  // 学生创建周报/月报草稿
  async create(req, res) {
    try {
      const { type = 'weekly', title, content } = req.body;
      if (!VALID_TYPES.includes(type)) return error(res, '类型仅支持 weekly/monthly', 400);
      if (!title) return error(res, '标题不能为空', 400);

      const assignment = await assignmentModel.findActiveByStudent(req.user.id);
      if (!assignment) return error(res, '你当前没有有效的实习分配，无法提交', 400);

      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const id = await internLogModel.create({
        student_id: req.user.id,
        assignment_id: assignment.id,
        plan_id: assignment.plan_id,
        teacher_id: assignment.teacher_id,
        type, title, content, file_url
      });
      const log = await internLogModel.findById(id);
      return success(res, log, '草稿已保存', 201);
    } catch (err) {
      return error(res, '创建失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const log = await internLogModel.findById(id);
      if (!log) return error(res, '记录不存在', 404);
      if (log.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (log.status !== 0) return error(res, '只有草稿可以修改', 400);

      const { title, content } = req.body;
      const file_url = req.file ? keyToUrl(req.file.filename) : undefined;
      await internLogModel.updateDraft(id, { title, content, file_url });
      const updated = await internLogModel.findById(id);
      return success(res, updated, '已更新');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  },

  async submit(req, res) {
    try {
      const id = Number(req.params.id);
      const log = await internLogModel.findById(id);
      if (!log) return error(res, '记录不存在', 404);
      if (log.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (![0, 3].includes(log.status)) return error(res, '当前状态不可提交', 400);
      await internLogModel.submit(id);
      const updated = await internLogModel.findById(id);
      return success(res, updated, '已提交');
    } catch (err) {
      return error(res, '提交失败：' + err.message, 500);
    }
  },

  // 教师批阅（通过/驳回）
  async review(req, res) {
    try {
      const id = Number(req.params.id);
      const log = await internLogModel.findById(id);
      if (!log) return error(res, '记录不存在', 404);
      if (log.teacher_id !== req.user.id) return error(res, '只能批阅自己指导学生的报告', 403);
      if (log.status !== 1) return error(res, '只有“已提交”的报告可以批阅', 400);

      const { agree, teacher_comment, reject_reason } = req.body;
      if (agree === undefined) return error(res, '请指定批阅结果', 400);
      if (!agree && !reject_reason) return error(res, '驳回时请填写原因', 400);

      await internLogModel.review(id, { agree, teacher_comment, reject_reason });
      const updated = await internLogModel.findById(id);
      await notify(log.student_id, '周报/月报批阅结果',
        `你的${log.type === 'monthly' ? '月报' : '周报'}「${log.title}」${agree ? '已通过' : '被驳回'}${!agree && reject_reason ? '：' + reject_reason : ''}`,
        agree ? 'success' : 'warning');
      return success(res, updated, agree ? '已通过' : '已驳回');
    } catch (err) {
      return error(res, '批阅失败：' + err.message, 500);
    }
  },

  // 周报/月报模板：学校可自定义,学生写日志时按模板填写
  async getTemplate(req, res) {
    try {
      const type = req.query.type === 'monthly' ? 'monthly' : 'weekly';
      const v = await systemConfigModel.get('log_template_' + type);
      return success(res, { type, template: v || DEFAULT_TPL[type] });
    } catch (e) { return error(res, e.message, 500); }
  },
  async setTemplate(req, res) {
    try {
      if (req.user.role > 2) return error(res, '权限不足', 403);
      const type = req.body.type === 'monthly' ? 'monthly' : 'weekly';
      await systemConfigModel.setMany({ ['log_template_' + type]: req.body.template || '' });
      return success(res, null, '模板已保存');
    } catch (e) { return error(res, e.message, 500); }
  },

  // 教师：批量批阅（一键通过/驳回多份）
  async batchReview(req, res) {
    try {
      const { ids, agree, teacher_comment, reject_reason } = req.body;
      if (!Array.isArray(ids) || !ids.length) return error(res, '请选择要批阅的报告', 400);
      if (agree === undefined) return error(res, '请指定批阅结果', 400);
      if (!agree && !reject_reason) return error(res, '批量驳回时请填写原因', 400);
      let ok = 0, skip = 0;
      for (const rawId of ids) {
        const id = Number(rawId);
        const log = await internLogModel.findById(id);
        if (!log || log.teacher_id !== req.user.id || log.status !== 1) { skip++; continue; }
        await internLogModel.review(id, { agree, teacher_comment, reject_reason });
        notify(log.student_id, '周报/月报批阅结果',
          `你的${log.type === 'monthly' ? '月报' : '周报'}「${log.title}」${agree ? '已通过' : '被驳回'}${!agree && reject_reason ? '：' + reject_reason : ''}`,
          agree ? 'success' : 'warning');
        ok++;
      }
      return success(res, { ok, skip }, `已批阅 ${ok} 份${skip ? `，跳过 ${skip} 份` : ''}`);
    } catch (err) {
      return error(res, '批量批阅失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const log = await internLogModel.findById(id);
      if (!log) return error(res, '记录不存在', 404);
      if (log.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (log.status !== 0) return error(res, '只有草稿可以删除', 400);
      await internLogModel.remove(id);
      return success(res, null, '已删除');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = internLogController;
