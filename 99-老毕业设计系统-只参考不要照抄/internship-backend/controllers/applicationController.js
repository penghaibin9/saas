const pool = require('../config/db');
const { applicationModel, positionModel, userModel, assignmentModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

// status 值：0待审核 1教师同意 2教师拒绝 3院校审核通过 4院校审核拒绝 5已录用 6未录用
const applicationController = {
  async list(req, res) {
    try {
      const { position_id, enterprise_id, status } = req.query;
      const user = req.user;

      const filter = {
        positionId:   position_id   !== undefined ? Number(position_id)   : undefined,
        enterpriseId: enterprise_id !== undefined ? Number(enterprise_id) : undefined,
        status:       status        !== undefined ? Number(status)        : undefined,
      };

      // 学生只能看自己的申请
      if (user.role === 4) filter.studentId = user.id;
      // 教师只能看分配给自己的申请
      if (user.role === 3) filter.teacherId = user.id;
      // 分院管理员只能看本学院的申请
      if (user.role === 2) filter.collegeId = user.collegeId;
      // 企业导师只能看投递到本企业的申请
      if (user.role === 5) filter.enterpriseId = user.enterpriseId || -1;

      const result = await applicationModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取申请列表成功');
    } catch (err) {
      return error(res, '获取申请列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const application = await applicationModel.findById(Number(req.params.id));
      if (!application) return error(res, '申请不存在', 404);

      const user = req.user;
      // 学生只能看自己的
      if (user.role === 4 && application.student_id !== user.id) return error(res, '权限不足', 403);
      // 教师只能看分配给自己的
      if (user.role === 3 && application.teacher_id !== user.id) return error(res, '权限不足', 403);

      return success(res, application, '获取申请详情成功');
    } catch (err) {
      return error(res, '获取申请详情失败：' + err.message, 500);
    }
  },

  // 学生提交申请
  async apply(req, res) {
    try {
      const { position_id, student_remark } = req.body;
      if (!position_id) return error(res, '岗位不能为空', 400);

      const position = await positionModel.findById(Number(position_id));
      if (!position) return error(res, '岗位不存在', 404);
      if (position.status !== 1) return error(res, '该岗位已下架', 400);

      const dup = await applicationModel.findByStudentAndPosition(req.user.id, Number(position_id));
      if (dup) return error(res, '已申请过该岗位', 409);

      const id = await applicationModel.create({
        student_id: req.user.id,
        position_id: Number(position_id),
        enterprise_id: position.enterprise_id,
        student_remark
      });
      const application = await applicationModel.findById(id);
      return success(res, application, '申请提交成功', 201);
    } catch (err) {
      return error(res, '申请提交失败：' + err.message, 500);
    }
  },

  // 教师审核（同意/拒绝）
  async teacherReview(req, res) {
    try {
      const id = Number(req.params.id);
      const application = await applicationModel.findById(id);
      if (!application) return error(res, '申请不存在', 404);
      if (application.teacher_id !== req.user.id) return error(res, '权限不足', 403);
      if (application.status !== 0) return error(res, '该申请已审核', 400);

      const { agree, opinion } = req.body;
      if (agree === undefined) return error(res, '请指定审核结果', 400);

      const status = agree ? 1 : 2;
      await applicationModel.updateStatus(id, { status, teacher_opinion: opinion });
      const updated = await applicationModel.findById(id);
      await notify(application.student_id, '实习申请审核结果',
        `你申请的「${updated.position_title || '岗位'}」${agree ? '已通过教师审核' : '被教师驳回'}${opinion ? '：' + opinion : ''}`,
        agree ? 'success' : 'warning');
      return success(res, updated, agree ? '已同意申请' : '已拒绝申请');
    } catch (err) {
      return error(res, '教师审核失败：' + err.message, 500);
    }
  },

  // 院校/分院管理员审核
  async adminReview(req, res) {
    try {
      const id = Number(req.params.id);
      const application = await applicationModel.findById(id);
      if (!application) return error(res, '申请不存在', 404);
      // 分院管理员只能审核本学院学生的申请
      if (req.user.role === 2 && application.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足，只能审核本学院学生的申请', 403);
      }
      if (application.status !== 1) return error(res, '申请未经教师同意，无法审核', 400);

      const { agree, opinion } = req.body;
      if (agree === undefined) return error(res, '请指定审核结果', 400);

      const status = agree ? 3 : 4;
      await applicationModel.updateStatus(id, { status, admin_opinion: opinion });
      const updated = await applicationModel.findById(id);
      await notify(application.student_id, '实习申请院校审核结果',
        `你申请的「${updated.position_title || '岗位'}」${agree ? '已通过院校审核' : '被院校驳回'}${opinion ? '：' + opinion : ''}`,
        agree ? 'success' : 'warning');
      return success(res, updated, agree ? '院校审核通过' : '院校审核拒绝');
    } catch (err) {
      return error(res, '管理员审核失败：' + err.message, 500);
    }
  },

  // 管理员登记录用结果（5已录用 / 6未录用），需先通过院校审核(status=3)
  async recruitResult(req, res) {
    try {
      const id = Number(req.params.id);
      const { recruited } = req.body;
      if (recruited === undefined) return error(res, '请指定录用结果', 400);

      const application = await applicationModel.findById(id);
      if (!application) return error(res, '申请不存在', 404);
      if (req.user.role === 2 && application.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足，只能登记本学院学生的录用结果', 403);
      }
      if (application.status !== 3) {
        return error(res, '该申请未通过院校审核，无法登记录用结果', 400);
      }

      if (recruited) {
        // 校验岗位招聘名额，避免超额录用
        const recruitedCount = await applicationModel.countByPositionAndStatus(application.position_id, 5);
        const headcount = Number(application.headcount) || 1;
        if (recruitedCount >= headcount) {
          return error(res, `该岗位招聘名额(${headcount})已满，无法继续录用`, 400);
        }
      }

      await applicationModel.updateStatus(id, { status: recruited ? 5 : 6 });
      const updated = await applicationModel.findById(id);

      // 录用后自动建立实习分配（幂等：已有有效分配则跳过）
      if (recruited) {
        try {
          const existing = await assignmentModel.findActiveByStudent(application.student_id);
          if (!existing) {
            const [plans] = await pool.query(
              `SELECT id FROM t_intern_plan WHERE status IN (2,3) AND is_deleted=0 ORDER BY id DESC LIMIT 1`
            );
            await assignmentModel.create({
              plan_id: plans.length ? plans[0].id : null,
              student_id: application.student_id,
              teacher_id: application.teacher_id || null,
              enterprise_id: application.enterprise_id
            });
          }
        } catch (e) { console.warn('[recruitResult] auto-assign fail:', e.message); }
      }

      await notify(application.student_id, '录用结果通知',
        `你申请的「${updated.position_title || '岗位'}」录用结果：${recruited ? '已录用，实习分配已建立' : '未录用'}`,
        recruited ? 'success' : 'info');
      return success(res, updated, recruited ? '已登记为录用，分配自动建立' : '已登记为未录用');
    } catch (err) {
      return error(res, '登记录用结果失败：' + err.message, 500);
    }
  },

  // 管理员分配指导教师
  async assignTeacher(req, res) {
    try {
      const id = Number(req.params.id);
      const { teacher_id } = req.body;
      if (!teacher_id) return error(res, '请指定指导教师', 400);

      const application = await applicationModel.findById(id);
      if (!application) return error(res, '申请不存在', 404);
      // 分院管理员只能为本学院学生分配教师
      if (req.user.role === 2 && application.student_college_id !== req.user.collegeId) {
        return error(res, '权限不足，只能管理本学院学生的申请', 403);
      }

      // 校验被分配对象确实是指导教师(role=3)，避免把任意用户设为教师
      const teacher = await userModel.findById(Number(teacher_id));
      if (!teacher || teacher.role !== 3) return error(res, '指定的指导教师无效', 400);
      if (req.user.role === 2 && teacher.college_id !== req.user.collegeId) {
        return error(res, '只能分配本学院的指导教师', 403);
      }

      await applicationModel.assignTeacher(id, Number(teacher_id));
      const updated = await applicationModel.findById(id);
      await notify(Number(teacher_id), '新的指导学生',
        `你被指派指导学生「${updated.student_name || ''}」的实习申请，请及时审核`, 'info');
      await notify(application.student_id, '已分配指导教师',
        `你的实习申请已分配指导教师：${teacher.real_name}`, 'info');
      return success(res, updated, '分配教师成功');
    } catch (err) {
      return error(res, '分配教师失败：' + err.message, 500);
    }
  },

  // 撤回申请（学生，仅限待审核状态）
  async withdraw(req, res) {
    try {
      const id = Number(req.params.id);
      const application = await applicationModel.findById(id);
      if (!application) return error(res, '申请不存在', 404);
      if (application.student_id !== req.user.id) return error(res, '权限不足', 403);
      if (application.status !== 0) return error(res, '已审核的申请无法撤回', 400);

      await applicationModel.remove(id);
      return success(res, null, '申请已撤回');
    } catch (err) {
      return error(res, '撤回申请失败：' + err.message, 500);
    }
  }
};

module.exports = applicationController;
