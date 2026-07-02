const { leaveModel, assignmentModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

function diffDays(start, end) {
  const s = new Date(start), e = new Date(end);
  if (isNaN(s) || isNaN(e)) return null;
  const d = Math.round((e - s) / 86400000) + 1;
  return d > 0 ? d : null;
}

const leaveController = {
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
      if (user.role === 5) filter.studentId = -1; // 企业导师无权查看全量请假（请用企业端）

      const result = await leaveModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取请假列表成功');
    } catch (err) {
      return error(res, '获取请假列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const lv = await leaveModel.findById(Number(req.params.id));
      if (!lv) return error(res, '请假记录不存在', 404);
      const user = req.user;
      if (user.role === 4 && lv.student_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 3 && lv.teacher_id !== user.id) return error(res, '权限不足', 403);
      if (user.role === 2 && lv.student_college_id !== user.collegeId) return error(res, '权限不足', 403);
      return success(res, lv, '获取详情成功');
    } catch (err) {
      return error(res, '获取详情失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { start_date, end_date, reason } = req.body;
      if (!start_date || !end_date) return error(res, '请假起止日期不能为空', 400);
      if (!reason) return error(res, '请假事由不能为空', 400);
      const days = diffDays(start_date, end_date);
      if (!days) return error(res, '请假日期不合法', 400);

      const assignment = await assignmentModel.findActiveByStudent(req.user.id);
      if (!assignment) return error(res, '你当前没有有效的实习分配，无法请假', 400);

      const id = await leaveModel.create({
        student_id: req.user.id,
        assignment_id: assignment.id,
        teacher_id: assignment.teacher_id,
        start_date, end_date, days, reason
      });
      const lv = await leaveModel.findById(id);
      return success(res, lv, '请假草稿已保存', 201);
    } catch (err) {
      return error(res, '创建请假失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const lv = await leaveModel.findById(id);
      if (!lv) return error(res, '请假记录不存在', 404);
      if (lv.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (lv.status !== 0) return error(res, '只有草稿可以修改', 400);

      const { start_date, end_date, reason } = req.body;
      let days;
      if (start_date && end_date) {
        days = diffDays(start_date, end_date);
        if (!days) return error(res, '请假日期不合法', 400);
      }
      await leaveModel.updateDraft(id, { start_date, end_date, days, reason });
      const updated = await leaveModel.findById(id);
      return success(res, updated, '已更新');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  },

  async submit(req, res) {
    try {
      const id = Number(req.params.id);
      const lv = await leaveModel.findById(id);
      if (!lv) return error(res, '请假记录不存在', 404);
      if (lv.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (![0, 3].includes(lv.status)) return error(res, '当前状态不可提交', 400);
      await leaveModel.submit(id);
      const updated = await leaveModel.findById(id);
      return success(res, updated, '已提交');
    } catch (err) {
      return error(res, '提交失败：' + err.message, 500);
    }
  },

  // 教师审批
  async review(req, res) {
    try {
      const id = Number(req.params.id);
      const lv = await leaveModel.findById(id);
      if (!lv) return error(res, '请假记录不存在', 404);
      if (lv.teacher_id !== req.user.id) return error(res, '只能审批自己指导学生的请假', 403);
      if (lv.status !== 1) return error(res, '只有“已提交”的请假可以审批', 400);

      const { agree, reject_reason } = req.body;
      if (agree === undefined) return error(res, '请指定审批结果', 400);
      if (!agree && !reject_reason) return error(res, '驳回时请填写原因', 400);

      await leaveModel.review(id, { agree, reject_reason });
      const updated = await leaveModel.findById(id);
      await notify(lv.student_id, '请假审批结果',
        `你的请假申请${agree ? '已通过' : '被驳回'}${!agree && reject_reason ? '：' + reject_reason : ''}`,
        agree ? 'success' : 'warning');
      return success(res, updated, agree ? '已通过' : '已驳回');
    } catch (err) {
      return error(res, '审批失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      const lv = await leaveModel.findById(id);
      if (!lv) return error(res, '请假记录不存在', 404);
      if (lv.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (lv.status !== 0) return error(res, '只有草稿可以删除', 400);
      await leaveModel.remove(id);
      return success(res, null, '已删除');
    } catch (err) {
      return error(res, '删除失败：' + err.message, 500);
    }
  }
};

module.exports = leaveController;
