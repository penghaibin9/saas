const { agreementModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

// 角色：1超管 2分院 3教师 4学生
const agreementController = {
  async list(req, res) {
    try {
      const user = req.user;
      const filter = {};
      if (req.query.status !== undefined) filter.status = Number(req.query.status);
      if (user.role === 4) filter.studentId = user.id;
      else if (user.role === 3) filter.teacherId = user.id;
      else if (user.role === 2) filter.collegeId = user.collegeId;
      const result = await agreementModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取协议列表成功');
    } catch (err) {
      return error(res, '获取协议列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const ag = await agreementModel.findById(Number(req.params.id));
      if (!ag) return error(res, '协议不存在', 404);
      const user = req.user;
      if (user.role === 4 && ag.student_id !== user.id) return error(res, '无权查看', 403);
      if (user.role === 3 && ag.teacher_id !== user.id) return error(res, '无权查看', 403);
      if (user.role === 2 && ag.college_id !== user.collegeId) return error(res, '无权查看', 403);
      return success(res, ag, '获取协议详情成功');
    } catch (err) {
      return error(res, '获取协议详情失败：' + err.message, 500);
    }
  },

  // 管理员/分院发起协议
  async create(req, res) {
    try {
      if (![1, 2].includes(req.user.role)) return error(res, '无权发起协议', 403);
      const { student_id, application_id, enterprise_id, position_id, teacher_id, title, content, start_date, end_date } = req.body;
      if (!student_id || !title) return error(res, '请填写学生与协议标题', 400);
      const student = await userModel.findById(Number(student_id));
      if (!student) return error(res, '学生不存在', 400);
      if (req.user.role === 2 && student.college_id !== req.user.collegeId) {
        return error(res, '只能为本学院学生发起协议', 403);
      }
      const id = await agreementModel.create({
        student_id: Number(student_id), application_id, enterprise_id, position_id, teacher_id,
        college_id: student.college_id, title, content, start_date, end_date
      });
      await notify(Number(student_id), '实习协议待签署', `请在线签署实习协议《${title}》`, 'info');
      if (teacher_id) await notify(Number(teacher_id), '实习协议待会签', `学生${student.real_name || ''}的实习协议《${title}》待您会签`, 'info');
      return success(res, { id }, '协议已发起', 201);
    } catch (err) {
      return error(res, '发起协议失败：' + err.message, 500);
    }
  },

  // 学生签署
  async studentSign(req, res) {
    try {
      const ag = await agreementModel.findById(Number(req.params.id));
      if (!ag) return error(res, '协议不存在', 404);
      if (req.user.role !== 4 || ag.student_id !== req.user.id) return error(res, '只能签署本人协议', 403);
      if (ag.status === 3) return error(res, '协议已作废', 400);
      if (ag.status === 2) return error(res, '协议已生效，无需再签', 400);
      const signName = (req.body && req.body.sign_name) || req.user.realName || '';
      await agreementModel.studentSign(ag.id, signName);
      if (ag.teacher_id) await notify(ag.teacher_id, '协议待会签', `学生已签署协议《${ag.title}》，请会签`, 'info');
      return success(res, null, '签署成功');
    } catch (err) {
      return error(res, '签署失败：' + err.message, 500);
    }
  },

  // 教师会签（需学生先签）
  async teacherSign(req, res) {
    try {
      const ag = await agreementModel.findById(Number(req.params.id));
      if (!ag) return error(res, '协议不存在', 404);
      const isOwner = req.user.role === 3 && ag.teacher_id === req.user.id;
      if (!isOwner && ![1, 2].includes(req.user.role)) return error(res, '无权会签', 403);
      if (ag.status === 3) return error(res, '协议已作废', 400);
      if (!ag.student_signed) return error(res, '请先等待学生签署', 400);
      await agreementModel.teacherSign(ag.id);
      return success(res, null, '会签成功');
    } catch (err) {
      return error(res, '会签失败：' + err.message, 500);
    }
  },

  // 校方盖章生效（需学生+教师均已签）
  async activate(req, res) {
    try {
      if (![1, 2].includes(req.user.role)) return error(res, '无权操作', 403);
      const ag = await agreementModel.findById(Number(req.params.id));
      if (!ag) return error(res, '协议不存在', 404);
      if (req.user.role === 2 && ag.college_id !== req.user.collegeId) return error(res, '无权操作', 403);
      if (ag.status === 3) return error(res, '协议已作废', 400);
      if (!ag.student_signed || !ag.teacher_signed) return error(res, '需学生与教师均已签署后方可盖章生效', 400);
      await agreementModel.schoolActivate(ag.id);
      await notify(ag.student_id, '实习协议已生效', `你的实习协议《${ag.title}》已三方签署生效`, 'success');
      if (ag.teacher_id) await notify(ag.teacher_id, '实习协议已生效', `协议《${ag.title}》已生效`, 'success');
      return success(res, null, '协议已盖章生效');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  async voidAgreement(req, res) {
    try {
      if (![1, 2].includes(req.user.role)) return error(res, '无权操作', 403);
      const ag = await agreementModel.findById(Number(req.params.id));
      if (!ag) return error(res, '协议不存在', 404);
      await agreementModel.voidAgreement(ag.id);
      return success(res, null, '协议已作废');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  }
};

module.exports = agreementController;
