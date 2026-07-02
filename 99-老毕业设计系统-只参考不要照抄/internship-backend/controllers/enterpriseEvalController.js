const crypto = require('crypto');
const { enterpriseEvalModel, userModel, assignmentModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');

const isAdmin = (u) => u.role === 1 || u.role === 2;

const enterpriseEvalController = {
  async list(req, res) {
    try {
      const u = req.user;
      const filter = {};
      if (req.query.status !== undefined) filter.status = Number(req.query.status);
      if (req.query.student_id) filter.studentId = Number(req.query.student_id);
      if (u.role === 2) filter.collegeId = u.collegeId;
      const result = await enterpriseEvalModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取企业评价列表成功');
    } catch (err) { return error(res, '获取失败：' + err.message, 500); }
  },

  // 管理员/教师为学生生成评价令牌（企业导师免登录填写）
  async create(req, res) {
    try {
      const u = req.user;
      if (!isAdmin(u) && u.role !== 3) return error(res, '无权操作', 403);
      const { student_id } = req.body;
      if (!student_id) return error(res, '请选择学生', 400);
      const student = await userModel.findById(Number(student_id));
      if (!student) return error(res, '学生不存在', 400);
      if (u.role === 2 && student.college_id !== u.collegeId) return error(res, '只能为本学院学生生成', 403);

      // 关联学生的有效实习分配（取企业）
      let enterprise_id = req.body.enterprise_id || null, assignment_id = null;
      const a = await assignmentModel.findActiveByStudent(Number(student_id));
      if (a) { enterprise_id = enterprise_id || a.enterprise_id; assignment_id = a.id; }

      const token = crypto.randomBytes(20).toString('hex');
      const id = await enterpriseEvalModel.create({
        student_id: Number(student_id), enterprise_id, assignment_id,
        college_id: student.college_id, token, mentor_name: req.body.mentor_name
      });
      // 评价链接：企业导师扫码/点击打开（前端可渲染评价表单页）
      const link = `${req.protocol}://${req.get('host')}/m/eval.html?token=${token}`;
      return success(res, { id, token, link }, '已生成企业评价链接', 201);
    } catch (err) { return error(res, '生成失败：' + err.message, 500); }
  },

  async remove(req, res) {
    try {
      if (!isAdmin(req.user) && req.user.role !== 3) return error(res, '无权操作', 403);
      await enterpriseEvalModel.remove(Number(req.params.id));
      return success(res, null, '已删除');
    } catch (err) { return error(res, '删除失败：' + err.message, 500); }
  },

  /* -------- 公开（免登录，凭 token） -------- */
  async publicGet(req, res) {
    try {
      const ev = await enterpriseEvalModel.findByToken(req.params.token);
      if (!ev) return error(res, '链接无效或已失效', 404);
      return success(res, {
        student_name: ev.student_name, enterprise_name: ev.enterprise_name,
        status: ev.status, mentor_name: ev.mentor_name,
        score_overall: ev.score_overall, score_attitude: ev.score_attitude,
        score_skill: ev.score_skill, score_discipline: ev.score_discipline, comment: ev.comment
      }, 'ok');
    } catch (err) { return error(res, '获取失败：' + err.message, 500); }
  },

  async publicSubmit(req, res) {
    try {
      const ev = await enterpriseEvalModel.findByToken(req.params.token);
      if (!ev) return error(res, '链接无效或已失效', 404);
      if (ev.status === 1) return error(res, '该评价已提交，无需重复填写', 400);
      const b = req.body;
      const clamp = (v) => { const n = Number(v); return (n >= 1 && n <= 5) ? n : null; };
      const affected = await enterpriseEvalModel.submitByToken(req.params.token, {
        mentor_name: b.mentor_name, mentor_title: b.mentor_title,
        score_overall: clamp(b.score_overall), score_attitude: clamp(b.score_attitude),
        score_skill: clamp(b.score_skill), score_discipline: clamp(b.score_discipline),
        comment: b.comment
      });
      if (!affected) return error(res, '提交失败', 400);
      return success(res, null, '评价提交成功，感谢您的反馈');
    } catch (err) { return error(res, '提交失败：' + err.message, 500); }
  }
};

module.exports = enterpriseEvalController;
