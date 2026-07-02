const { complaintModel, userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { notify } = require('../utils/notify');

// 投诉/异常/安全上报控制器。category: complaint投诉 / incident异常 / safety安全
const complaintController = {
  // 列表：管理员看全校/本院；教师看本院；学生看自己上报的
  async list(req, res) {
    try {
      const user = req.user;
      const filter = {
        status:   req.query.status   !== undefined ? Number(req.query.status)   : undefined,
        category: req.query.category,
        keyword:  req.query.keyword
      };
      if (user.role === 4) filter.reporterId = user.id;          // 学生：自己上报的
      else if (user.role === 2 || user.role === 3) filter.collegeId = user.collegeId; // 分院/教师：本院
      // 院校管理员(1)：全量

      const result = await complaintModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取上报列表成功');
    } catch (err) {
      return error(res, '获取上报列表失败：' + err.message, 500);
    }
  },

  async overview(req, res) {
    try {
      const collegeId = req.user.role === 1 ? null : req.user.collegeId;
      const data = await complaintModel.countByStatus(collegeId);
      return success(res, data, '获取统计成功');
    } catch (err) {
      return error(res, '获取统计失败：' + err.message, 500);
    }
  },

  // 上报（任意登录用户均可，学生为主）
  async create(req, res) {
    try {
      const { category, title, content, contact_phone, urgency, student_id } = req.body || {};
      if (!title) return error(res, '请填写标题', 400);

      const user = req.user;
      // 学生上报默认关联自己；其他角色可指定学生
      const sid = user.role === 4 ? user.id : (student_id || null);
      const id = await complaintModel.create({
        category, title, content, contact_phone,
        urgency: urgency !== undefined ? Number(urgency) : 1,
        student_id: sid, reporter_id: user.id, reporter_role: user.role,
        college_id: user.collegeId || null
      });

      // 通知院校管理员及时处理（安全/异常类更紧急）
      try {
        const admins = await userModel.findAll({ role: 1 }, { page: 1, pageSize: 50 });
        const catText = category === 'safety' ? '安全事件' : category === 'incident' ? '异常情况' : '投诉';
        for (const a of (admins.list || [])) {
          await notify(a.id, `新的${catText}上报`, `「${title}」需要处理，请尽快查看`, 'warning');
        }
      } catch (_) {}

      return success(res, { id }, '上报已提交，学校将尽快处理');
    } catch (err) {
      return error(res, '上报失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const c = await complaintModel.findById(Number(req.params.id));
      if (!c) return error(res, '记录不存在', 404);
      // 学生只能看自己上报的
      if (req.user.role === 4 && c.reporter_id !== req.user.id) return error(res, '权限不足', 403);
      return success(res, c, '获取详情成功');
    } catch (err) {
      return error(res, '获取详情失败：' + err.message, 500);
    }
  },

  // 处理（管理员/教师）
  async handle(req, res) {
    try {
      const c = await complaintModel.findById(Number(req.params.id));
      if (!c) return error(res, '记录不存在', 404);
      // 分院/教师仅可处理本院
      if ((req.user.role === 2 || req.user.role === 3) && c.college_id && c.college_id !== req.user.collegeId) {
        return error(res, '只能处理本学院的上报', 403);
      }
      const status = Number(req.body.status);
      if (![1, 2, 3].includes(status)) return error(res, '处理状态不合法', 400);

      await complaintModel.handle(Number(req.params.id), {
        status, handle_remark: req.body.handle_remark, handler_id: req.user.id
      });

      // 通知上报人处理进展
      if (c.reporter_id) {
        const stText = status === 1 ? '处理中' : status === 2 ? '已处理' : '已关闭';
        await notify(c.reporter_id, '上报处理进展', `您上报的「${c.title}」状态更新为：${stText}`, 'info');
      }
      return success(res, null, '处理已记录');
    } catch (err) {
      return error(res, '处理失败：' + err.message, 500);
    }
  }
};

module.exports = complaintController;
