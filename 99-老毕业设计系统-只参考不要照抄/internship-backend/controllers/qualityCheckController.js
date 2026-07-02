const pool = require('../config/db');
const { qualityCheckModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

const qualityCheckController = {
  async list(req, res) {
    try {
      const { status, scope, student_id } = req.query;
      const user = req.user;
      const filter = {
        status: status !== undefined ? Number(status) : undefined,
        scope,
        studentId: student_id !== undefined ? Number(student_id) : undefined,
      };
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 3) filter.checkerId = user.id;     // 教师看分配给自己的检查任务
      if (user.role === 4) filter.studentId = user.id;     // 学生看针对自己的检查

      const result = await qualityCheckModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取质量检查列表成功');
    } catch (err) {
      return error(res, '获取质量检查列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const item = await qualityCheckModel.findById(Number(req.params.id));
      if (!item) return error(res, '检查记录不存在', 404);
      const user = req.user;
      if (user.role === 3 && item.checker_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 4 && item.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && item.college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, item, '获取检查详情成功');
    } catch (err) {
      return error(res, '获取检查详情失败：' + err.message, 500);
    }
  },

  // 单条配对
  async create(req, res) {
    try {
      const { batch_name, student_id, checker_id, check_type, scope, achievement_id } = req.body;
      if (!batch_name || !student_id) return error(res, '批次名称与待查学生不能为空', 400);
      const college_id = req.user.role === 2 ? req.user.collegeId : (req.body.college_id || null);
      const id = await qualityCheckModel.create({
        batch_name, student_id: Number(student_id), checker_id: checker_id ? Number(checker_id) : null,
        check_type, scope, achievement_id: achievement_id ? Number(achievement_id) : null, college_id
      });
      const item = await qualityCheckModel.findById(id);
      return success(res, item, '已创建检查任务', 201);
    } catch (err) {
      return error(res, '创建检查任务失败：' + err.message, 500);
    }
  },

  /**
   * 一键生成检查学生任务清单
   * body: { batch_name, check_type(census/sample), scope(self/cross),
   *         checker_ids: [教师id...], student_ids: [学生id...], sample_rate(抽查比例 0-1) }
   * 将学生轮转分配给检查教师；抽查时按比例随机抽取学生。
   */
  async generate(req, res) {
    let conn;
    try {
      const { batch_name, check_type = 'census', scope = 'cross', checker_ids = [], sample_rate } = req.body;
      let { student_ids = [] } = req.body;
      if (!batch_name) return error(res, '批次名称不能为空', 400);
      if (!Array.isArray(checker_ids) || !checker_ids.length) return error(res, '请提供检查教师列表', 400);
      if (!Array.isArray(student_ids) || !student_ids.length) return error(res, '请提供待查学生列表', 400);

      // 抽查：按比例随机抽取
      if (check_type === 'sample') {
        const rate = Math.min(Math.max(Number(sample_rate) || 0.3, 0.01), 1);
        const shuffled = [...student_ids].sort(() => Math.random() - 0.5);
        student_ids = shuffled.slice(0, Math.max(1, Math.round(student_ids.length * rate)));
      }

      const college_id = req.user.role === 2 ? req.user.collegeId : (req.body.college_id || null);
      conn = await pool.getConnection();
      await conn.beginTransaction();
      let created = 0;
      for (let i = 0; i < student_ids.length; i++) {
        const checkerId = checker_ids[i % checker_ids.length]; // 轮转分配
        await qualityCheckModel.create({
          batch_name, check_type, scope,
          checker_id: Number(checkerId), student_id: Number(student_ids[i]),
          college_id
        }, conn);
        created++;
      }
      await conn.commit();
      return success(res, { created, total_students: student_ids.length }, `已生成 ${created} 条检查任务`);
    } catch (err) {
      if (conn) { try { await conn.rollback(); } catch (_) { /* ignore */ } }
      return error(res, '生成检查任务失败：' + err.message, 500);
    } finally {
      if (conn) conn.release();
    }
  },

  // 教师审阅（自查/互查）：1通过 2驳回 3未完成
  async review(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await qualityCheckModel.findById(id);
      if (!item) return error(res, '检查记录不存在', 404);
      if (item.checker_id !== req.user.id) return error(res, '只能审阅分配给你的检查任务', 403);

      const { status, opinion } = req.body;
      const st = Number(status);
      if (![1, 2, 3].includes(st)) return error(res, '审阅结果无效（1通过 2驳回 3未完成）', 400);
      if (st === 2 && !opinion) return error(res, '驳回时请填写意见', 400);

      await qualityCheckModel.review(id, { status: st, opinion });
      const updated = await qualityCheckModel.findById(id);
      const msg = st === 1 ? '已通过' : st === 2 ? '已驳回' : '已标记未完成';
      await notify(item.student_id, '毕业设计质量检查结果',
        `你的毕业设计质量检查（${item.batch_name}）${msg}${st === 2 && opinion ? '：' + opinion : ''}`,
        st === 1 ? 'success' : 'warning');
      return success(res, updated, msg);
    } catch (err) {
      return error(res, '审阅失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await qualityCheckModel.findById(id);
      if (!item) return error(res, '检查记录不存在', 404);
      await qualityCheckModel.remove(id);
      return success(res, null, '已删除');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = qualityCheckController;
