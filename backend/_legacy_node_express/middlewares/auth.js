require('dotenv').config();
const jwt = require('jsonwebtoken');
const { error } = require('../utils/response');
const tenancy = require('../config/tenancy');

const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '7d';

// 安全：JWT 密钥必须由环境变量提供。生产环境缺失或过短时拒绝启动。
let JWT_SECRET = process.env.JWT_SECRET;
if (!JWT_SECRET || JWT_SECRET.length < 32) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('启动失败：生产环境必须在 .env 中配置至少 32 位的 JWT_SECRET');
  }
  console.warn('⚠️  未配置安全的 JWT_SECRET（建议 >=32 位随机字符串），当前使用临时开发密钥，请勿用于生产环境');
  JWT_SECRET = JWT_SECRET || 'school-lifecycle-dev-secret-change-in-production';
}

// 角色映射（兼容旧系统 1-5，全生命周期沿用）
const ROLE_MAP = {
  1: '院校管理员',
  2: '分院管理员',
  3: '指导教师',
  4: '学生',
  5: '企业导师',
};

function createToken(user) {
  const payload = {
    id: user.id,
    username: user.username,
    role: user.role,
    roleName: ROLE_MAP[user.role] || '未知角色',
    realName: user.real_name,
    collegeId: user.college_id,
    enterpriseId: user.enterprise_id || null,
    // 全生命周期：登录主体若为学生，绑定 student_id（BASE-P3）
    studentId: user.student_id || null,
    mustChangePassword: Boolean(user.must_change_password),
  };

  // SaaS：把当前请求所属租户写入令牌，后续请求据此自动路由到该校独立库
  const t = tenancy.currentTenant();
  if (t && t.code) payload.tid = t.code;

  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
}

function authMiddleware(req, res, next) {
  const authHeader = req.headers.authorization || '';
  const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : authHeader;

  if (!token) return error(res, '未提供认证令牌', 401);

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    // SaaS 安全：令牌所属租户必须与当前请求解析出的租户一致，杜绝跨校令牌复用
    if (tenancy.MODE === 'multi') {
      const cur = tenancy.currentTenant();
      if (cur && decoded.tid && decoded.tid !== cur.code) {
        return error(res, '令牌与当前学校不匹配，请重新登录', 403, { code: 'TENANT_MISMATCH' });
      }
    }
    req.user = decoded;
    next();
  } catch (err) {
    return error(res, '认证令牌无效或已过期', 401);
  }
}

function requireRole(...roles) {
  const allowed = roles.flat();
  return (req, res, next) => {
    if (!req.user) return error(res, '未提供认证令牌', 401);
    if (!allowed.includes(req.user.role)) return error(res, '权限不足', 403);
    next();
  };
}

// 未完成首次改密前，仅放行改密/查看个人信息等少数接口。
function requirePasswordChanged(req, res, next) {
  if (req.user && req.user.mustChangePassword) {
    return error(res, '请先修改初始密码后再使用其他功能', 403, { code: 'MUST_CHANGE_PASSWORD' });
  }
  next();
}

module.exports = {
  authMiddleware,
  requireRole,
  requirePasswordChanged,
  createToken,
  ROLE_MAP,
  JWT_SECRET,
};
