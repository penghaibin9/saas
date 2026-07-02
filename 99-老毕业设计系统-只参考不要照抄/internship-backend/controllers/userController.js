const pwdHash = require('../utils/password');
const dayjs = require('dayjs');
const { userModel } = require('../models');
const { success, error } = require('../utils/response');
const { createToken, ROLE_MAP } = require('../middlewares/auth');
const { isValidEmail, isValidPhone, isStrongPassword } = require('../utils/validate');

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
    enterpriseId: user.enterprise_id || null,
    majorId: user.major_id,
    classId: user.class_id,
    eeid: user.eeid,
    status: user.status,
    skillTags: user.skill_tags || '',
    emergencyName: user.emergency_name || '',
    emergencyPhone: user.emergency_phone || '',
    emergencyRelation: user.emergency_relation || '',
    lastLoginTime: user.last_login_time
      ? dayjs(user.last_login_time).format('YYYY-MM-DD HH:mm:ss')
      : null,
    createTime: user.create_time
      ? dayjs(user.create_time).format('YYYY-MM-DD HH:mm:ss')
      : null
  };
}

function validateRegisterBody(body) {
  const { username, password, real_name } = body;

  if (!username || !password || !real_name) {
    return '用户名、密码和真实姓名不能为空';
  }

  if (username.length < 3 || username.length > 50) {
    return '用户名长度需在 3-50 个字符之间';
  }

  if (password.length < 6) {
    return '密码长度不能少于 6 位';
  }

  if (body.phone && !isValidPhone(body.phone)) {
    return '手机号格式不正确';
  }

  if (body.email && !isValidEmail(body.email)) {
    return '邮箱格式不正确';
  }

  return null;
}

const userController = {
  async register(req, res) {
    try {
      const validationError = validateRegisterBody(req.body);
      if (validationError) {
        return error(res, validationError, 400);
      }

      const {
        username,
        password,
        real_name,
        phone,
        email,
        college_id,
        major_id,
        class_id,
        eeid
      } = req.body;

      const existing = await userModel.findByUsername(username);
      if (existing) {
        return error(res, '用户名已存在', 409);
      }

      // SaaS 配额：学生数达套餐上限则拒绝注册（single 模式不限）
      if (await require('../utils/tenantQuota').studentQuotaExceeded()) {
        return error(res, '学生数已达套餐配额上限，请联系学校管理员或平台升级套餐', 403);
      }

      const hashedPassword = await pwdHash.hash(password);
      // 安全：公开注册一律为学生(role=4)，禁止前端自带 role 提权为管理员/教师。
      // 管理员、教师等账号只能由管理员后台创建或 Excel 导入。
      const userId = await userModel.create({
        username,
        password: hashedPassword,
        real_name,
        phone,
        email,
        role: 4,
        college_id,
        major_id,
        class_id,
        eeid
      });

      const user = await userModel.findById(userId);
      return success(res, sanitizeUser(user), '注册成功', 201);
    } catch (err) {
      return error(res, '注册失败：' + err.message, 500);
    }
  },

  async login(req, res) {
    try {
      const { username, password } = req.body;

      if (!username || !password) {
        return error(res, '用户名和密码不能为空', 400);
      }

      const user = await userModel.findByUsername(username);
      if (!user) {
        return error(res, '用户名或密码错误', 401);
      }

      if (user.status !== 1) {
        return error(res, '账号已被禁用，请联系管理员', 403);
      }

      const isMatch = await pwdHash.compare(password, user.password);
      if (!isMatch) {
        return error(res, '用户名或密码错误', 401);
      }

      const mustChangePassword = Boolean(user.must_change_password);
      const token = createToken(user);

      await userModel.updateLastLoginTime(user.id);

      return success(res, {
        token,
        mustChangePassword,
        user: sanitizeUser(user)
      }, mustChangePassword ? '登录成功，请修改初始密码' : '登录成功');
    } catch (err) {
      return error(res, '登录失败：' + err.message, 500);
    }
  },

  async getProfile(req, res) {
    try {
      const user = await userModel.findById(req.user.id);
      if (!user) {
        return error(res, '用户不存在', 404);
      }

      return success(res, sanitizeUser(user), '获取用户信息成功');
    } catch (err) {
      return error(res, '获取用户信息失败：' + err.message, 500);
    }
  },

  async updateProfile(req, res) {
    try {
      const { real_name, phone, email, skill_tags, emergency_name, emergency_phone, emergency_relation } = req.body;
      if (!real_name) return error(res, '姓名不能为空', 400);
      if (phone && !isValidPhone(phone)) return error(res, '手机号格式不正确', 400);
      if (email && !isValidEmail(email)) return error(res, '邮箱格式不正确', 400);
      const fields = { real_name, phone: phone || null, email: email || null };
      if (skill_tags !== undefined && req.user.role === 4) fields.skill_tags = skill_tags || null;
      if (req.user.role === 4) {
        if (emergency_name !== undefined) fields.emergency_name = emergency_name || null;
        if (emergency_phone !== undefined) {
          if (emergency_phone && !isValidPhone(emergency_phone)) return error(res, '紧急联系人电话格式不正确', 400);
          fields.emergency_phone = emergency_phone || null;
        }
        if (emergency_relation !== undefined) fields.emergency_relation = emergency_relation || null;
      }
      await userModel.updateInfo(req.user.id, fields);
      const updated = await userModel.findById(req.user.id);
      return success(res, sanitizeUser(updated), '个人信息更新成功');
    } catch (err) {
      return error(res, '更新失败：' + err.message, 500);
    }
  },

  async changePassword(req, res) {
    try {
      const { oldPassword, newPassword } = req.body;

      if (!oldPassword || !newPassword) {
        return error(res, '原密码和新密码不能为空', 400);
      }

      if (!isStrongPassword(newPassword)) {
        return error(res, '新密码至少 6 位，且须为数字与字母的组合', 400);
      }

      const user = await userModel.findByUsername(req.user.username);
      if (!user) {
        return error(res, '用户不存在', 404);
      }

      if (oldPassword === newPassword) {
        return error(res, '新密码不能与原密码相同', 400);
      }

      const isMatch = await pwdHash.compare(oldPassword, user.password);
      if (!isMatch) {
        return error(res, '原密码错误', 400);
      }

      const hashedPassword = await pwdHash.hash(newPassword);
      // updatePassword 默认清除 must_change_password 标记
      await userModel.updatePassword(user.id, hashedPassword);

      // 下发新令牌，使前端立即解除“强制改密”状态
      const fresh = await userModel.findById(user.id);
      const token = createToken(fresh);
      return success(res, { token }, '密码修改成功');
    } catch (err) {
      return error(res, '密码修改失败：' + err.message, 500);
    }
  }
};

module.exports = userController;
