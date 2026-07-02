const permModel = require('../models/permModel');
const { error } = require('../utils/response');

/**
 * 细粒度权限中间件（自定义角色引擎）。供新接口按权限码控制，不影响既有 requireRole。
 * 院校管理员(role=1)视为超管放行；否则按用户被授予的自定义角色权限判定。
 */
function requirePermission(code) {
  return async (req, res, next) => {
    if (!req.user) return error(res, '未提供认证令牌', 401);
    if (req.user.role === 1) return next(); // 超管放行
    try {
      const { perms } = await permModel.getUserPerms(req.user.id);
      if (permModel.hasPermission(perms, code)) return next();
      return error(res, '权限不足（缺少 ' + code + '）', 403);
    } catch (e) {
      return error(res, '权限校验失败：' + e.message, 500);
    }
  };
}

/** 解析当前用户的数据范围并挂到 req.dataScope（控制器据此过滤） */
async function attachDataScope(req, res, next) {
  try {
    if (req.user && req.user.role === 1) { req.dataScope = { scope: 'all', filter: {} }; return next(); }
    const { scope } = await permModel.getUserPerms(req.user.id);
    req.dataScope = { scope, filter: permModel.scopeToFilter(scope, req.user) };
    next();
  } catch (e) { req.dataScope = { scope: 'self', filter: { userId: req.user.id } }; next(); }
}

module.exports = { requirePermission, attachDataScope };
