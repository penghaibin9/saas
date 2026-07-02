const { gdAchievementModel, gdTopicModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { createUploader, keyToUrl } = require('../utils/upload');
const { notify } = require('../utils/notify');

const upload = createUploader({ prefix: 'gdwork' });

const gdAchievementController = {
  upload: upload.single('file'),

  async list(req, res) {
    try {
      const { status, student_id } = req.query;
      const user = req.user;
      const filter = {
        status: status !== undefined ? Number(status) : undefined,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
      };
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看毕设成果

      const result = await gdAchievementModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取成果列表成功');
    } catch (err) {
      return error(res, '获取成果列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await gdAchievementModel.findById(Number(req.params.id));
      if (!item) return error(res, '成果不存在', 404);
      const user = req.user;
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && item.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && item.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取成果详情成功');
    } catch (err) {
      return error(res, '获取成果详情失败：' + err.message, 500);
    }
  },

  // 学生上传成果（自动关联其选题及指导老师）
  async create(req, res) {
    try {
      const { title, link, doc_type } = req.body;
      if (!title) return error(res, '成果标题不能为空', 400);

      // 取该学生的选题以关联指导老师
      const topics = await gdTopicModel.findAll({ studentId: req.user.id }, { page: 1, pageSize: 1 });
      const topic = topics.list[0];

      const file_url = req.file ? keyToUrl(req.file.filename) : null;
      const dt = doc_type || 'other';
      const version = await gdAchievementModel.nextVersion(req.user.id, dt);
      const id = await gdAchievementModel.create({
        student_id: req.user.id,
        topic_id: topic ? topic.id : null,
        teacher_id: topic ? topic.teacher_id : null,
        title, link, file_url, doc_type: dt, version
      });
      const item = await gdAchievementModel.findById(id);
      return success(res, item, '成果已提交，等待审阅', 201);
    } catch (err) {
      return error(res, '提交成果失败：' + err.message, 500);
    }
  },

  // 学生重新提交（被驳回/未完成后）
  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdAchievementModel.findById(id);
      if (!item) return error(res, '成果不存在', 404);
      if (item.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (item.status === 1) return error(res, '已通过的成果不可修改', 400);

      const { title, link, doc_type } = req.body;
      const file_url = req.file ? keyToUrl(req.file.filename) : undefined;
      await gdAchievementModel.update(id, { title, link, file_url, doc_type });
      const updated = await gdAchievementModel.findById(id);
      return success(res, updated, '已重新提交，等待审阅');
    } catch (err) {
      return error(res, '更新成果失败：' + err.message, 500);
    }
  },

  // 教师审阅：1通过 2驳回 3未完成
  async review(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdAchievementModel.findById(id);
      if (!item) return error(res, '成果不存在', 404);
      if (item.teacher_id !== req.user.id) return error(res, '只能审阅自己指导学生的成果', 403);

      const { status, reject_reason } = req.body;
      const st = Number(status);
      if (![1, 2, 3].includes(st)) return error(res, '审阅结果无效（1通过 2驳回 3未完成）', 400);
      if (st === 2 && !reject_reason) return error(res, '驳回时请填写原因', 400);

      await gdAchievementModel.review(id, { status: st, reject_reason });
      const updated = await gdAchievementModel.findById(id);
      const msg = st === 1 ? '已通过' : st === 2 ? '已驳回' : '已标记未完成';
      await notify(item.student_id, '毕业设计成果审阅结果',
        `你的成果「${item.title}」${msg}${st === 2 && reject_reason ? '：' + reject_reason : ''}`,
        st === 1 ? 'success' : 'warning');
      return success(res, updated, msg);
    } catch (err) {
      return error(res, '审阅失败：' + err.message, 500);
    }
  },

  // 版本历史：某学生某文档类型(开题/中期/初稿/定稿)的全部版本
  async versions(req, res) {
    try {
      const docType = req.query.doc_type || 'other';
      const studentId = req.user.role === 4 ? req.user.id : Number(req.query.student_id);
      if (!studentId) return error(res, '请指定学生', 400);
      const list = await gdAchievementModel.listVersions(studentId, docType);
      return success(res, { list }, '获取版本历史成功');
    } catch (err) {
      return error(res, '获取版本历史失败：' + err.message, 500);
    }
  },

  // 教师批注：对某一版本写批改意见(不改变通过/驳回状态)
  async annotate(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdAchievementModel.findById(id);
      if (!item) return error(res, '成果不存在', 404);
      if (req.user.role === 3 && item.teacher_id !== req.user.id) return error(res, '只能批注自己指导学生的成果', 403);
      if (req.user.role > 3) return error(res, '权限不足', 403);
      const comment = (req.body.comment || '').trim();
      if (!comment) return error(res, '批注内容不能为空', 400);
      await gdAchievementModel.annotate(id, comment);
      await notify(item.student_id, '毕业设计成果有新批注',
        `指导老师对你的「${item.title}」(v${item.version}) 作了批注,请查看`, 'info');
      return success(res, null, '批注已保存');
    } catch (err) {
      return error(res, '批注失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await gdAchievementModel.findById(id);
      if (!item) return error(res, '成果不存在', 404);
      if (req.user.role === 4 && item.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (req.user.role === 4 && item.status === 1) return error(res, '已通过的成果不可删除', 400);
      await gdAchievementModel.remove(id);
      return success(res, null, '已删除');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = gdAchievementController;
