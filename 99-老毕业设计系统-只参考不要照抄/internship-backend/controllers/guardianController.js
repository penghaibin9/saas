const guardianModel = require('../models/guardianModel');
const { userModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { isValidPhone } = require('../utils/validate');

function clientIp(req) { return (req.headers['x-forwarded-for'] || '').split(',')[0].trim() || req.ip || ''; }
function publicView(g) {
  // 公开视图：仅返回签署所需信息，隐藏内部字段
  return {
    token: g.token, title: g.title, content: g.content,
    studentName: g.student_name, studentEeid: g.student_eeid,
    signStatus: g.sign_status, signName: g.sign_name, signedAt: g.signed_at,
    expired: g.expires_at ? new Date(g.expires_at) < new Date() : false,
  };
}

const guardianController = {
  // ── 校内：发起/管理 ──
  async create(req, res) {
    try {
      if (![1, 2, 3].includes(req.user.role)) return error(res, '仅教师/管理员可发起家长签署', 403);
      const { student_id, title, content, guardian_name, guardian_phone, relation, valid_days } = req.body;
      if (!student_id || !title || !content) return error(res, '学生、标题、正文不能为空', 400);
      const stu = await userModel.findById(Number(student_id));
      if (!stu || stu.role !== 4) return error(res, '学生不存在', 404);
      if (req.user.role === 2 && stu.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      if (guardian_phone && !isValidPhone(guardian_phone)) return error(res, '家长手机号格式不正确', 400);
      const days = Number(valid_days);
      const expires_at = Number.isFinite(days) && days > 0
        ? new Date(Date.now() + days * 86400000).toISOString().slice(0, 19).replace('T', ' ')
        : null;
      const { id, token } = await guardianModel.create({
        student_id: Number(student_id), title, content, guardian_name, guardian_phone, relation,
        expires_at, created_by: req.user.id,
      });
      return success(res, { id, token, signPath: `/m/guardian.html?token=${token}` }, '已生成家长签署链接', 201);
    } catch (e) { return error(res, '发起失败：' + e.message, 500); }
  },

  async list(req, res) {
    try {
      const u = req.user;
      const filter = { status: req.query.status !== undefined ? Number(req.query.status) : undefined };
      if (u.role === 4) filter.studentId = u.id;
      else if (u.role === 2) filter.collegeId = u.collegeId;
      else if (u.role === 5) return error(res, '权限不足', 403);
      const result = await guardianModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取家长签署列表成功');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  async detail(req, res) {
    try {
      const g = await guardianModel.findById(Number(req.params.id));
      if (!g) return error(res, '记录不存在', 404);
      const u = req.user;
      if (u.role === 4 && g.student_id !== u.id) return error(res, '权限不足', 403);
      if (u.role === 2 && g.college_id !== u.collegeId) return error(res, '权限不足', 403);
      return success(res, g, '获取详情成功');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  async remove(req, res) {
    try {
      if (![1, 2].includes(req.user.role)) return error(res, '仅管理员可删除', 403);
      const g = await guardianModel.findById(Number(req.params.id));
      if (!g) return error(res, '记录不存在', 404);
      if (req.user.role === 2 && g.college_id !== req.user.collegeId) return error(res, '权限不足', 403);
      await guardianModel.remove(Number(req.params.id));
      return success(res, null, '已删除');
    } catch (e) { return error(res, '删除失败：' + e.message, 500); }
  },

  // ── 公开：家长凭令牌查看/签署（免登录） ──
  async publicGet(req, res) {
    try {
      const g = await guardianModel.findByToken(req.params.token);
      if (!g) return error(res, '链接无效或已失效', 404);
      return success(res, publicView(g), '获取签署信息成功');
    } catch (e) { return error(res, '获取失败：' + e.message, 500); }
  },

  async publicSign(req, res) {
    try {
      const g = await guardianModel.findByToken(req.params.token);
      if (!g) return error(res, '链接无效或已失效', 404);
      if (g.sign_status !== 0) return error(res, '该知情同意书已处理，请勿重复提交', 409);
      if (g.expires_at && new Date(g.expires_at) < new Date()) return error(res, '签署链接已过期', 410);

      const { agree, sign_name, guardian_name, guardian_phone, relation, reject_reason } = req.body;
      if (guardian_phone && !isValidPhone(guardian_phone)) return error(res, '家长手机号格式不正确', 400);

      if (agree === false) {
        const n = await guardianModel.reject(req.params.token, { reason: reject_reason, ip: clientIp(req), ua: req.headers['user-agent'] });
        if (!n) return error(res, '提交失败，可能已被处理', 409);
        return success(res, null, '已记录您的不同意意见');
      }
      if (!sign_name || !String(sign_name).trim()) return error(res, '请填写签署人姓名', 400);
      const n = await guardianModel.sign(req.params.token, {
        sign_name: String(sign_name).trim().slice(0, 50),
        guardian_name, guardian_phone, relation,
        ip: clientIp(req), ua: req.headers['user-agent'],
      });
      if (!n) return error(res, '提交失败，可能已被处理', 409);
      return success(res, null, '签署成功，感谢您的确认');
    } catch (e) { return error(res, '签署失败：' + e.message, 500); }
  },
};

module.exports = guardianController;
