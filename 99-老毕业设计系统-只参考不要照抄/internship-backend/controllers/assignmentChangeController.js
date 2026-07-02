const { assignmentChangeModel, assignmentModel, userModel, enterpriseModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

const TYPE_TEXT = { transfer: '换岗', terminate: '终止实习', complete: '结束实习' };
const ST_TEXT = { 0: '待教师审批', 1: '待管理员审批', 2: '已执行', 3: '已驳回' };

const assignmentChangeController = {
  async list(req, res) {
    try {
      const filter = {
        status: req.query.status !== undefined ? Number(req.query.status) : undefined,
        changeType: req.query.change_type
      };
      const user = req.user;
      if (user.role === 4) filter.studentId = user.id;
      else if (user.role === 3) filter.teacherId = user.id;
      else if (user.role === 2) filter.collegeId = user.collegeId;

      const result = await assignmentChangeModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取换岗/终止申请成功');
    } catch (err) {
      return error(res, '获取列表失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { assignment_id, change_type, new_enterprise_id, new_teacher_id, reason } = req.body || {};
      if (!assignment_id || !change_type) return error(res, '请指定分配记录与变更类型', 400);
      if (!['transfer', 'terminate'].includes(change_type)) return error(res, '变更类型无效', 400);
      if (!reason || !String(reason).trim()) return error(res, '请填写申请原因', 400);

      const assignment = await assignmentModel.findById(Number(assignment_id));
      if (!assignment || assignment.status !== 1) return error(res, '当前无有效实习分配', 400);

      const user = req.user;
      if (user.role === 4 && assignment.student_id !== user.id) return error(res, '只能为自己申请', 403);
      if (user.role === 3 && assignment.teacher_id !== user.id) return error(res, '只能为本组学生发起', 403);

      if (change_type === 'transfer') {
        if (!new_enterprise_id) return error(res, '换岗请指定新实习单位', 400);
        const ent = await enterpriseModel.findById(Number(new_enterprise_id));
        if (!ent) return error(res, '新实习单位不存在', 404);
      }

      const pending = await assignmentChangeModel.findPendingByStudent(assignment.student_id);
      if (pending) return error(res, '该学生已有进行中的换岗/终止申请', 400);

      const id = await assignmentChangeModel.create({
        assignment_id: assignment.id,
        student_id: assignment.student_id,
        change_type,
        old_enterprise_id: assignment.enterprise_id,
        new_enterprise_id: change_type === 'transfer' ? Number(new_enterprise_id) : null,
        new_teacher_id: new_teacher_id ? Number(new_teacher_id) : null,
        reason: String(reason).trim(),
        applicant_id: user.id,
        applicant_role: user.role
      });

      if (assignment.teacher_id) {
        await notify(assignment.teacher_id, '换岗/终止待审批',
          `学生 ${assignment.student_name || ''} 提交了${TYPE_TEXT[change_type]}申请，请及时处理`, 'warning', { sms: change_type === 'terminate' });
      }

      const item = await assignmentChangeModel.findById(id);
      return success(res, item, '申请已提交，等待指导教师审批', 201);
    } catch (err) {
      return error(res, '提交失败：' + err.message, 500);
    }
  },

  async teacherReview(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await assignmentChangeModel.findById(id);
      if (!item) return error(res, '申请不存在', 404);
      if (item.status !== 0) return error(res, '当前状态不可教师审批', 400);
      if (req.user.role === 3 && item.teacher_id !== req.user.id) return error(res, '只能审批自己指导的学生', 403);
      if (req.user.role !== 1 && req.user.role !== 2 && req.user.role !== 3) return error(res, '权限不足', 403);

      const approve = req.body && (req.body.approve === true || req.body.approve === 'true' || req.body.approve === 1);
      const opinion = req.body && req.body.opinion ? String(req.body.opinion).slice(0, 255) : null;
      const newStatus = approve ? 1 : 3;
      await assignmentChangeModel.updateStatus(id, newStatus, {
        teacher_opinion: opinion,
        teacher_id: req.user.id
      });

      if (approve) {
        const admins = await userModel.findAll({ role: 1 }, { page: 1, pageSize: 20 });
        for (const a of (admins.list || [])) {
          await notify(a.id, '换岗/终止待终审',
            `${item.student_name} 的${TYPE_TEXT[item.change_type]}申请已通过教师审批`, 'info');
        }
      } else if (item.student_id) {
        await notify(item.student_id, '换岗/终止申请被驳回',
          `您的${TYPE_TEXT[item.change_type]}申请未通过教师审批${opinion ? '：' + opinion : ''}`, 'info');
      }

      return success(res, null, approve ? '已提交管理员终审' : '已驳回');
    } catch (err) {
      return error(res, '审批失败：' + err.message, 500);
    }
  },

  async adminReview(req, res) {
    try {
      const id = Number(req.params.id);
      const item = await assignmentChangeModel.findById(id);
      if (!item) return error(res, '申请不存在', 404);
      if (item.status !== 1) return error(res, '当前状态不可管理员终审', 400);
      if (req.user.role === 2 && item.student_college_id !== req.user.collegeId) {
        return error(res, '只能审批本学院申请', 403);
      }
      if (req.user.role !== 1 && req.user.role !== 2) return error(res, '权限不足', 403);

      const approve = req.body && (req.body.approve === true || req.body.approve === 'true' || req.body.approve === 1);
      const opinion = req.body && req.body.opinion ? String(req.body.opinion).slice(0, 255) : null;

      if (!approve) {
        await assignmentChangeModel.updateStatus(id, 3, { admin_opinion: opinion, handler_id: req.user.id });
        if (item.student_id) {
          await notify(item.student_id, '换岗/终止申请被驳回',
            `您的${TYPE_TEXT[item.change_type]}申请未通过管理员审批${opinion ? '：' + opinion : ''}`, 'info', { sms: true });
        }
        return success(res, null, '已驳回');
      }

      if (item.change_type === 'terminate') {
        await assignmentModel.remove(item.assignment_id);
      } else {
        await assignmentModel.update(item.assignment_id, {
          enterprise_id: item.new_enterprise_id,
          teacher_id: item.new_teacher_id !== undefined && item.new_teacher_id !== null
            ? item.new_teacher_id : undefined
        });
      }

      await assignmentChangeModel.updateStatus(id, 2, { admin_opinion: opinion, handler_id: req.user.id });

      if (item.student_id) {
        await notify(item.student_id, '换岗/终止已生效',
          `您的${TYPE_TEXT[item.change_type]}申请已执行${item.change_type === 'transfer' ? '，请留意新单位打卡范围' : ''}`,
          'success', { sms: true });
        if (item.teacher_id) {
          await notify(item.teacher_id, '换岗/终止已执行',
            `学生 ${item.student_name} 的${TYPE_TEXT[item.change_type]}申请已生效`, 'info');
        }
      }

      return success(res, null, '已执行变更');
    } catch (err) {
      return error(res, '终审失败：' + err.message, 500);
    }
  },

  overview(req, res) {
    return assignmentChangeController.list(req, res);
  }
};

assignmentChangeController.ST_TEXT = ST_TEXT;
assignmentChangeController.TYPE_TEXT = TYPE_TEXT;

module.exports = assignmentChangeController;
