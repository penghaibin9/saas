const pwdHash = require('../utils/password');
const dayjs = require('dayjs');
const { userModel } = require('../models');
const { success, error } = require('../utils/response');
const { ROLE_MAP } = require('../middlewares/auth');
const { isValidEmail, isValidPhone, clampPagination } = require('../utils/validate');

const VALID_ROLES = [1, 2, 3, 4];

function sanitizeUser(user) {
  return {
    id: user.id,
    username: user.username,
    realName: user.real_name,
    phone: user.phone,
    email: user.email,
    role: user.role,
    roleName: ROLE_MAP[user.role] || '未知角色',
    collegeId: user.college_id,
    majorId: user.major_id,
    classId: user.class_id,
    eeid: user.eeid,
    status: user.status,
    lastLoginTime: user.last_login_time
      ? dayjs(user.last_login_time).format('YYYY-MM-DD HH:mm:ss') : null,
    createTime: user.create_time
      ? dayjs(user.create_time).format('YYYY-MM-DD HH:mm:ss') : null
  };
}

// 分院管理员(role=2)只能操作本学院用户；院校管理员(role=1)不受限。
function outOfScope(actor, targetUser) {
  return actor.role === 2 && targetUser.college_id !== actor.collegeId;
}

const adminUserController = {
  async list(req, res) {
    try {
      const { role, college_id, class_id, status, keyword } = req.query;
      // 分院管理员只能查看本学院用户，忽略其传入的 college_id
      const collegeId = req.user.role === 2
        ? req.user.collegeId
        : (college_id !== undefined ? Number(college_id) : undefined);
      const result = await userModel.findAll(
        {
          role:      role       !== undefined ? Number(role)       : undefined,
          collegeId,
          classId:   class_id   !== undefined ? Number(class_id)   : undefined,
          status:    status     !== undefined ? Number(status)     : undefined,
          keyword
        },
        clampPagination(req.query)
      );
      result.list = result.list.map(sanitizeUser);
      return success(res, result, '获取用户列表成功');
    } catch (err) {
      return error(res, '获取用户列表失败：' + err.message, 500);
    }
  },

  async detail(req, res) {
    try {
      const user = await userModel.findById(Number(req.params.id));
      if (!user) return error(res, '用户不存在', 404);
      if (outOfScope(req.user, user)) return error(res, '权限不足，只能查看本学院用户', 403);
      return success(res, sanitizeUser(user), '获取用户信息成功');
    } catch (err) {
      return error(res, '获取用户信息失败：' + err.message, 500);
    }
  },

  async create(req, res) {
    try {
      const { username, password = '123456', real_name, phone, email, role, major_id, class_id, eeid } = req.body;
      let { college_id } = req.body;
      if (!username || !real_name || !role) return error(res, '用户名、真实姓名和角色不能为空', 400);
      if (typeof password !== 'string' || password.length < 6) return error(res, '密码不能少于6位', 400);

      const roleNum = Number(role);
      if (!VALID_ROLES.includes(roleNum)) return error(res, '角色无效', 400);
      if (phone && !isValidPhone(phone)) return error(res, '手机号格式不正确', 400);
      if (email && !isValidEmail(email)) return error(res, '邮箱格式不正确', 400);

      // 分院管理员只能在本学院创建指导教师/学生，禁止创建管理员账号(提权)
      if (req.user.role === 2) {
        if (![3, 4].includes(roleNum)) return error(res, '分院管理员只能创建指导教师或学生账号', 403);
        college_id = req.user.collegeId;
      }

      const existing = await userModel.findByUsername(username);
      if (existing) return error(res, '用户名已存在', 409);

      // SaaS 配额：创建学生时校验套餐学生数上限（single 模式不限）
      if (roleNum === 4 && await require('../utils/tenantQuota').studentQuotaExceeded()) {
        return error(res, '学生数已达套餐配额上限，请联系平台升级套餐', 403);
      }

      const hashedPassword = await pwdHash.hash(password);
      // 管理员创建的账号使用初始密码，首次登录强制改密
      const userId = await userModel.create({
        username, password: hashedPassword, real_name, phone, email,
        role: roleNum, college_id, major_id, class_id, eeid,
        must_change_password: 1
      });
      const user = await userModel.findById(userId);
      return success(res, sanitizeUser(user), '创建用户成功', 201);
    } catch (err) {
      return error(res, '创建用户失败：' + err.message, 500);
    }
  },

  async update(req, res) {
    try {
      const id = Number(req.params.id);
      const user = await userModel.findById(id);
      if (!user) return error(res, '用户不存在', 404);
      if (outOfScope(req.user, user)) return error(res, '权限不足，只能管理本学院用户', 403);

      if (req.body.phone && !isValidPhone(req.body.phone)) return error(res, '手机号格式不正确', 400);
      if (req.body.email && !isValidEmail(req.body.email)) return error(res, '邮箱格式不正确', 400);

      // 不允许通过此接口直接改密码 / 软删除标记等敏感字段（updateInfo 已白名单，这里再防 role 提权）
      const { role, password, ...rest } = req.body;
      const fields = { ...rest };
      if (role !== undefined) {
        const roleNum = Number(role);
        if (!VALID_ROLES.includes(roleNum)) return error(res, '角色无效', 400);
        if (req.user.role === 2 && ![3, 4].includes(roleNum)) {
          return error(res, '分院管理员不能将用户设为管理员', 403);
        }
        fields.role = roleNum;
      }
      // 分院管理员不得把用户迁移到其他学院
      if (req.user.role === 2) fields.college_id = req.user.collegeId;

      await userModel.updateInfo(id, fields);
      const updated = await userModel.findById(id);
      return success(res, sanitizeUser(updated), '更新用户成功');
    } catch (err) {
      return error(res, '更新用户失败：' + err.message, 500);
    }
  },

  async resetPassword(req, res) {
    try {
      const id = Number(req.params.id);
      const user = await userModel.findById(id);
      if (!user) return error(res, '用户不存在', 404);
      if (outOfScope(req.user, user)) return error(res, '权限不足，只能管理本学院用户', 403);

      const newPassword = req.body.password || '123456';
      if (typeof newPassword !== 'string' || newPassword.length < 6) return error(res, '密码不能少于6位', 400);
      const hashed = await pwdHash.hash(newPassword);
      // 重置后要求用户下次登录强制改密
      await userModel.updatePassword(id, hashed, { mustChange: 1 });
      return success(res, null, '重置密码成功');
    } catch (err) {
      return error(res, '重置密码失败：' + err.message, 500);
    }
  },

  async toggleStatus(req, res) {
    try {
      const id = Number(req.params.id);
      const user = await userModel.findById(id);
      if (!user) return error(res, '用户不存在', 404);
      if (id === req.user.id) return error(res, '不能禁用自己', 400);
      if (outOfScope(req.user, user)) return error(res, '权限不足，只能管理本学院用户', 403);

      const newStatus = user.status === 1 ? 0 : 1;
      await userModel.updateInfo(id, { status: newStatus });
      return success(res, { status: newStatus }, newStatus === 1 ? '启用成功' : '禁用成功');
    } catch (err) {
      return error(res, '操作失败：' + err.message, 500);
    }
  },

  async remove(req, res) {
    try {
      const id = Number(req.params.id);
      if (id === req.user.id) return error(res, '不能删除自己', 400);
      const user = await userModel.findById(id);
      if (!user) return error(res, '用户不存在', 404);
      await userModel.remove(id);
      return success(res, null, '删除用户成功');
    } catch (err) {
      return error(res, '删除用户失败：' + err.message, 500);
    }
  }
};

module.exports = adminUserController;
