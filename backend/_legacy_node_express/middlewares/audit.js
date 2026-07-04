const auditLogModel = require('../models/auditLogModel');

/**
 * 操作审计中间件 — 移植自旧系统
 * 在响应结束后(res 'finish')异步落库，记录写操作的完整责任链。
 * 原则：fire-and-forget，任何异常只打印日志，绝不影响主业务响应。
 */

const AUDIT_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

const SENSITIVE_KEYS = new Set([
  'password', 'oldPassword', 'newPassword', 'old_password', 'new_password',
  'confirmPassword', 'confirm_password', 'pwd', 'token', 'secret', 'access_token',
]);

// 资源段 → 中文名（覆盖全生命周期底座 + 实践教学核心）
const RESOURCE_LABELS = {
  'users': '用户', 'admin/users': '账号', 'students': '学生主档', 'colleges': '学院',
  'majors': '专业', 'classes': '班级', 'enterprises': '企业', 'positions': '岗位',
  'module-licenses': '模块授权', 'tenants': '租户', 'roles': '角色', 'perms': '权限',
  'applications': '录用申请', 'reports': '周报', 'notifications': '通知',
  'intern-plans': '实习计划', 'assignments': '实习分配', 'checkins': '打卡',
  'intern-logs': '实习日志', 'leaves': '请假', 'announcements': '公告',
  'gd-tasks': '毕设任务', 'gd-topics': '毕设选题', 'gd-grades': '毕设成绩',
  'gd-achievements': '毕设成果', 'quality-checks': '质量检查',
  'insurances': '保险', 'agreements': '实习协议', 'defense': '答辩',
  'enterprise-evals': '企业评价', 'complaints': '投诉', 'audit-logs': '审计日志',
  'files': '文件', 'todos': '待办', 'messages': '消息',
};

const SUBACTION_LABELS = {
  'login': '登录', 'logout': '登出', 'register': '注册', 'approve': '审核通过',
  'reject': '驳回', 'audit': '审核', 'sign': '签署', 'confirm': '确认',
  'submit': '提交', 'cancel': '取消', 'read': '标记已读', 'read-all': '全部已读',
  'reset-password': '重置密码', 'change-password': '修改密码', 'import': '批量导入',
  'assign': '分配', 'grade': '评分', 'publish': '发布', 'revoke': '作废',
  'handle': '处理', 'resolve': '处理完成', 'switch': '切换身份',
};

const METHOD_VERBS = { POST: '新增', PUT: '修改', PATCH: '修改', DELETE: '删除' };

/** 从请求路径推断可读操作描述、对象类型与对象ID。兼容 /api 与 /api/v1 前缀。 */
function resolveAction(method, originalUrl) {
  const pathOnly = (originalUrl || '').split('?')[0];
  const segments = pathOnly.replace(/^\/api(\/v\d+)?\/?/, '').split('/').filter(Boolean);
  if (segments.length === 0) return { action: `${method} ${pathOnly}`, targetType: null, targetId: null };

  let resourceKey = segments[0];
  let consumed = 1;
  const twoSeg = `${segments[0]}/${segments[1] || ''}`;
  if (RESOURCE_LABELS[twoSeg]) { resourceKey = twoSeg; consumed = 2; }
  const resourceLabel = RESOURCE_LABELS[resourceKey] || resourceKey;

  let targetId = null;
  const rest = segments.slice(consumed);
  if (rest.length && /^\d+$/.test(rest[0])) { targetId = rest[0]; rest.shift(); }

  const sub = rest.filter((s) => !/^\d+$/.test(s)).pop();
  let verb;
  if (sub && SUBACTION_LABELS[sub]) verb = SUBACTION_LABELS[sub];
  else verb = METHOD_VERBS[method] || method;

  return { action: `${verb}${resourceLabel}`, targetType: resourceKey, targetId };
}

function sanitize(body) {
  if (!body || typeof body !== 'object') return null;
  let json;
  try {
    json = JSON.stringify(body, (key, value) => (SENSITIVE_KEYS.has(key) ? '***' : value));
  } catch (_) {
    return null;
  }
  if (json === '{}' || json === 'null') return null;
  return json.length > 2000 ? json.slice(0, 2000) + '…' : json;
}

function getClientIp(req) {
  const xff = req.headers['x-forwarded-for'];
  if (xff) return String(xff).split(',')[0].trim();
  return req.ip || req.connection?.remoteAddress || null;
}

function auditMiddleware(req, res, next) {
  if (!AUDIT_METHODS.has(req.method)) return next();

  const bodyUsername = req.body && (req.body.username || req.body.account);

  res.on('finish', () => {
    try {
      const u = req.user || {};
      const { action, targetType, targetId } = resolveAction(req.method, req.originalUrl);
      auditLogModel.create({
        user_id: u.id || null,
        username: u.username || bodyUsername || null,
        real_name: u.realName || null,
        role: u.role ?? null,
        college_id: u.collegeId ?? null,
        ip: getClientIp(req),
        method: req.method,
        path: (req.originalUrl || '').split('?')[0].slice(0, 255),
        action,
        target_type: targetType,
        target_id: targetId,
        status_code: res.statusCode,
        success: res.statusCode >= 200 && res.statusCode < 400 ? 1 : 0,
        detail: sanitize(req.body),
      }).catch((e) => console.warn('审计日志写入失败:', e.message));
    } catch (e) {
      console.warn('审计日志处理异常:', e.message);
    }
  });

  next();
}

module.exports = { auditMiddleware, resolveAction };
