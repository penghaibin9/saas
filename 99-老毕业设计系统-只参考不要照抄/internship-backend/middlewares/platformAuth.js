/**
 * 平台运营管理员鉴权（控制面专用，独立于租户登录）
 * 凭 PLATFORM_ADMIN_TOKEN（Bearer）访问。未配置该环境变量则控制台默认关闭（403），
 * 安全缺省——避免误开放跨租户运营接口。强烈建议同时用 nginx 限制来源 IP/内网。
 */
const { error } = require('../utils/response');

function requirePlatformAdmin(req, res, next) {
  const expected = process.env.PLATFORM_ADMIN_TOKEN;
  if (!expected) return error(res, '平台运营控制台未启用（未配置 PLATFORM_ADMIN_TOKEN）', 403);
  const auth = req.headers.authorization || '';
  const token = auth.startsWith('Bearer ') ? auth.slice(7) : auth;
  if (!token || token !== expected) return error(res, '平台运营令牌无效', 401);
  req.platformOperator = req.headers['x-operator'] || 'platform';
  next();
}

module.exports = { requirePlatformAdmin };
