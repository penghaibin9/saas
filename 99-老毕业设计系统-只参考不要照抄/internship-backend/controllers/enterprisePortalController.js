const pwdHash = require('../utils/password');
const pool = require('../config/db');
const { enterpriseModel, userModel, positionModel, applicationModel, assignmentModel, checkinModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

/**
 * 企业端自助门户控制器。
 * 闭环：企业公开注册(register) → 管理员审核(enterpriseController.audit) →
 *      企业登录 → 发布岗位(createPosition) → 确认录用(confirmHire)。
 * 企业导师为角色 5，其数据范围严格限定在 token 中的 enterpriseId。
 */
const enterprisePortalController = {
  /** 公开：企业入驻注册（创建待审核企业 + 停用状态的企业导师账号）。 */
  async register(req, res) {
    const {
      enterprise_name, short_name, industry, address,
      contact_name, contact_phone, contact_email, description,
      username, password
    } = req.body || {};

    if (!enterprise_name || !contact_name || !contact_phone) {
      return error(res, '请填写企业名称、联系人与联系电话', 400);
    }
    if (!username || !password || String(password).length < 6) {
      return error(res, '请设置登录账号与至少 6 位的密码', 400);
    }

    try {
      const existing = await userModel.findByUsername(username);
      if (existing) return error(res, '该登录账号已被占用，请更换', 409);

      // 1) 创建待审核企业
      const enterpriseId = await enterpriseModel.create({
        name: enterprise_name, short_name, industry, address,
        contact_name, contact_phone, contact_email, description,
        audit_status: 0
      });

      // 2) 创建企业导师账号（停用，待审核通过后激活）
      const hashed = await pwdHash.hash(String(password));
      try {
        await userModel.create({
          username, password: hashed, real_name: contact_name,
          phone: contact_phone, email: contact_email,
          role: 5, enterprise_id: enterpriseId, status: 0, must_change_password: 0
        });
      } catch (e) {
        // 账号创建失败则回滚企业，避免产生孤立企业
        await enterpriseModel.remove(enterpriseId);
        throw e;
      }

      // 3) 通知管理员审核（给所有院校管理员发站内信）
      try {
        const admins = await userModel.findAll({ role: 1 }, { page: 1, pageSize: 50 });
        for (const a of (admins.list || [])) {
          await notify(a.id, '企业入驻待审核', `企业「${enterprise_name}」提交了入驻申请，请及时审核`, 'info');
        }
      } catch (_) { /* 通知失败不影响注册 */ }

      return success(res, { enterpriseId }, '入驻申请已提交，请等待学校管理员审核');
    } catch (err) {
      return error(res, '入驻申请失败：' + err.message, 500);
    }
  },

  /** 企业导师：我的企业信息与审核状态。 */
  async me(req, res) {
    try {
      if (!req.user.enterpriseId) return error(res, '当前账号未绑定企业', 400);
      const ent = await enterpriseModel.findById(req.user.enterpriseId);
      if (!ent) return error(res, '企业不存在', 404);
      return success(res, ent, '获取企业信息成功');
    } catch (err) {
      return error(res, '获取企业信息失败：' + err.message, 500);
    }
  },

  /** 企业导师：我发布的岗位列表。 */
  async listPositions(req, res) {
    try {
      const result = await positionModel.findAll(
        { enterpriseId: req.user.enterpriseId }, clampPagination(req.query)
      );
      return success(res, result, '获取岗位列表成功');
    } catch (err) {
      return error(res, '获取岗位列表失败：' + err.message, 500);
    }
  },

  /** 企业导师：发布岗位（强制绑定本企业，初始为待审核/未上架 status=0）。 */
  async createPosition(req, res) {
    try {
      const { title, description, requirement, salary, headcount, location, start_date, end_date, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline } = req.body || {};
      if (!title) return error(res, '请填写岗位名称', 400);
      const id = await positionModel.create({
        enterprise_id: req.user.enterpriseId,
        title, description, requirement, salary, headcount, location, start_date, end_date, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline
      });
      // 企业自助发布的岗位需学校审核后上架
      await positionModel.update(id, { status: 0 });
      return success(res, { id }, '岗位已提交，待学校审核上架');
    } catch (err) {
      return error(res, '发布岗位失败：' + err.message, 500);
    }
  },

  /** 企业导师：更新本企业岗位（仅限自己企业的岗位）。 */
  async updatePosition(req, res) {
    try {
      const pos = await positionModel.findById(Number(req.params.id));
      if (!pos) return error(res, '岗位不存在', 404);
      if (pos.enterprise_id !== req.user.enterpriseId) return error(res, '无权操作该岗位', 403);
      const { title, description, requirement, salary, headcount, location, start_date, end_date, tags,
        intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline } = req.body || {};
      // 企业不可自行改 status（上架权在学校），只允许改岗位内容
      await positionModel.update(Number(req.params.id),
        { title, description, requirement, salary, headcount, location, start_date, end_date, tags,
          intern_type, major_req, edu_req, work_time, welfare, to_regular, deadline });
      return success(res, null, '岗位已更新');
    } catch (err) {
      return error(res, '更新岗位失败：' + err.message, 500);
    }
  },

  /** 企业导师：收到的录用申请（投递到本企业岗位的申请）。 */
  async listApplications(req, res) {
    try {
      const status = req.query.status !== undefined ? Number(req.query.status) : undefined;
      const result = await applicationModel.findAll(
        { enterpriseId: req.user.enterpriseId, status }, clampPagination(req.query)
      );
      return success(res, result, '获取申请列表成功');
    } catch (err) {
      return error(res, '获取申请列表失败：' + err.message, 500);
    }
  },

  /**
   * 企业导师：确认录用 / 不录用。
   * 仅可对本企业、且已通过院校审核(status=3)的申请操作。
   */
  async confirmHire(req, res) {
    try {
      const app = await applicationModel.findById(Number(req.params.id));
      if (!app) return error(res, '申请不存在', 404);
      if (app.enterprise_id !== req.user.enterpriseId) return error(res, '无权操作该申请', 403);
      if (app.status !== 3) return error(res, '仅可对“院校审核通过”的申请确认录用', 400);

      const hired = req.body && (req.body.hired === true || req.body.hired === 'true' || req.body.hired === 1);
      const newStatus = hired ? 5 : 6;
      await applicationModel.updateStatus(Number(req.params.id), {
        status: newStatus,
        admin_opinion: req.body && req.body.remark ? String(req.body.remark).slice(0, 255) : undefined
      });

      // 录用后自动建立实习分配记录（幂等：已有有效分配则跳过）
      if (hired) {
        try {
          const existing = await assignmentModel.findActiveByStudent(app.student_id);
          if (!existing) {
            const [plans] = await pool.query(
              `SELECT id FROM t_intern_plan WHERE status IN (2,3) AND is_deleted=0 ORDER BY id DESC LIMIT 1`
            );
            await assignmentModel.create({
              plan_id: plans.length ? plans[0].id : null,
              student_id: app.student_id,
              teacher_id: app.teacher_id || null,
              enterprise_id: app.enterprise_id
            });
          }
        } catch (e) { console.warn('[confirmHire] auto-assign fail:', e.message); }
      }

      // 通知学生
      const title = hired ? '录用确认通知' : '录用结果通知';
      const content = hired
        ? `恭喜！企业已确认录用你的岗位申请「${app.position_title || ''}」，实习分配已自动建立`
        : `企业未录用你的岗位申请「${app.position_title || ''}」，可继续投递其他岗位`;
      if (app.student_id) await notify(app.student_id, title, content, hired ? 'success' : 'info');

      return success(res, null, hired ? '已确认录用，实习分配已建立' : '已标记不录用');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  /** 企业工作台概览：岗位数、待确认申请、在册实习生、今日打卡。 */
  async dashboard(req, res) {
    try {
      const entId = req.user.enterpriseId;
      if (!entId) return error(res, '当前账号未绑定企业', 400);
      const [[pos]] = await pool.query(
        'SELECT COUNT(*) AS total, SUM(CASE WHEN status=1 THEN 1 ELSE 0 END) AS active FROM t_position WHERE enterprise_id=? AND is_deleted=0', [entId]);
      const [[apps]] = await pool.query(
        `SELECT COUNT(*) AS pending FROM t_application a JOIN t_position p ON a.position_id=p.id
         WHERE p.enterprise_id=? AND a.is_deleted=0 AND a.status=3`, [entId]);
      const [[interns]] = await pool.query(
        'SELECT COUNT(*) AS total FROM t_assignment WHERE enterprise_id=? AND status=1 AND is_deleted=0', [entId]);
      const today = new Date().toISOString().slice(0, 10);
      const checkins = await checkinModel.findAll(
        { enterpriseId: entId, dateFrom: today + ' 00:00:00', dateTo: today + ' 23:59:59' },
        { page: 1, pageSize: 1 }
      );
      return success(res, {
        positions: Number(pos.total) || 0,
        positionsActive: Number(pos.active) || 0,
        pendingApplications: Number(apps.pending) || 0,
        internCount: Number(interns.total) || 0,
        todayCheckins: checkins.total || 0
      }, '获取概览成功');
    } catch (err) {
      return error(res, '获取概览失败：' + err.message, 500);
    }
  },

  /** 在册实习生列表。 */
  async listInterns(req, res) {
    try {
      const result = await assignmentModel.findAll(
        { enterpriseId: req.user.enterpriseId, status: 1 }, clampPagination(req.query)
      );
      return success(res, result, '获取实习生列表成功');
    } catch (err) {
      return error(res, '获取实习生列表失败：' + err.message, 500);
    }
  },

  /** 本企业实习生打卡记录（只读，默认今日）。 */
  async listCheckins(req, res) {
    try {
      const filter = { enterpriseId: req.user.enterpriseId };
      if (req.query.today !== '0') {
        const today = new Date().toISOString().slice(0, 10);
        filter.dateFrom = today + ' 00:00:00';
        filter.dateTo = today + ' 23:59:59';
      }
      const result = await checkinModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取打卡记录成功');
    } catch (err) {
      return error(res, '获取打卡记录失败：' + err.message, 500);
    }
  }
};

module.exports = enterprisePortalController;
