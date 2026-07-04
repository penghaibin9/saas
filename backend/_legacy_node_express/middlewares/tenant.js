const jwt = require('jsonwebtoken');
const tenancy = require('../config/tenancy');
const { JWT_SECRET } = require('./auth');
const { error } = require('../utils/response');

/**
 * 租户解析中间件（挂在 /api 之前，包裹整条请求链）— 移植自旧系统
 * single 模式：恒为默认租户，零开销。
 * multi  模式：按优先级解析"学校(租户)"：
 *   1) X-Tenant 头 / ?tenant= 查询
 *   2) 子域名 schoolA.example.com → schoolA
 *   3) JWT 的 tid 声明
 *   4) 登录体 body.tenantCode
 */
async function tenantMiddleware(req, res, next) {
  if (tenancy.MODE === 'single') {
    return tenancy.runWithTenant(tenancy.defaultTenant(), () => next());
  }

  if (req.path === '/health') return next();

  let code = req.headers['x-tenant'] || req.query.tenant || (req.body && req.body.tenantCode);

  if (!code) {
    const host = (req.headers.host || '').split(':')[0];
    const parts = host.split('.');
    if (parts.length > 2 && !/^\d+$/.test(parts[0])) code = parts[0];
  }

  if (!code) {
    const authHeader = req.headers.authorization || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : authHeader;
    if (token) {
      try { const d = jwt.decode(token); if (d && d.tid) code = d.tid; } catch (_) {}
    }
  }

  if (!code) {
    return error(res, '未指定学校(租户)。请通过子域名访问或携带 X-Tenant。', 400, { code: 'TENANT_REQUIRED' });
  }

  const tenant = await tenancy.resolveTenant(code);
  if (!tenant) {
    return error(res, `学校(租户)不存在或未开通：${code}`, 404, { code: 'TENANT_NOT_FOUND' });
  }
  if (tenant.status !== 1) {
    return error(res, '该学校账号已停用，请联系平台。', 403, { code: 'TENANT_DISABLED' });
  }

  return tenancy.runWithTenant(tenant, () => next());
}

module.exports = { tenantMiddleware };
