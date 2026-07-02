/**
 * CAS 2.0/3.0 票据校验（标准 serviceValidate 接口）
 */
class CasError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = 'CasError';
    this.status = status;
    this.code = code;
  }
}

async function validateCasTicket(validateBaseUrl, service, ticket) {
  if (!validateBaseUrl) {
    throw new CasError('CAS 已启用但未配置校验地址', 503, 'CAS_VALIDATE_URL_MISSING');
  }
  if (!ticket || !String(ticket).trim()) {
    throw new CasError('缺少 CAS ticket', 400, 'CAS_TICKET_MISSING');
  }

  const base = validateBaseUrl.replace(/\/$/, '');
  const url = `${base}?service=${encodeURIComponent(service)}&ticket=${encodeURIComponent(ticket)}`;
  let res;
  try {
    res = await fetch(url);
  } catch (_) {
    throw new CasError('CAS 校验服务暂不可用', 502, 'CAS_UPSTREAM_UNAVAILABLE');
  }
  const text = await res.text();
  if (!res.ok) throw new CasError('CAS 校验服务返回异常', 502, 'CAS_UPSTREAM_ERROR');

  if (text.includes('authenticationFailure') || text.includes('INVALID_TICKET')) {
    throw new CasError('CAS 票据无效或已过期', 401, 'CAS_TICKET_INVALID');
  }
  const isSuccess = /<(?:cas:|)authenticationSuccess[\s>]/i.test(text);
  const userMatch = text.match(/<(?:cas:|)user>([^<]+)<\/(?:cas:|)user>/i);
  if (isSuccess && userMatch && userMatch[1].trim()) return userMatch[1].trim();

  throw new CasError('CAS 校验响应无有效用户标识', 401, 'CAS_IDENTITY_MISSING');
}

function buildCasLoginUrl(casLoginUrl, service) {
  const sep = casLoginUrl.includes('?') ? '&' : '?';
  return `${casLoginUrl}${sep}service=${encodeURIComponent(service)}`;
}

function configuredReturnToOrigins() {
  const raw = process.env.CAS_RETURN_TO_ALLOWLIST || process.env.CAS_RETURN_TO_ORIGINS || '';
  const origins = new Set();
  for (const item of raw.split(',').map((value) => value.trim()).filter(Boolean)) {
    try {
      const url = new URL(item);
      if (url.protocol === 'http:' || url.protocol === 'https:') origins.add(url.origin);
    } catch (_) { /* 忽略无效配置项，默认拒绝 */ }
  }
  return origins;
}

/**
 * 将 returnTo 收敛为可安全重定向的绝对地址。
 * 默认仅接受本站根相对路径；跨域地址必须由环境变量显式列入 origin 白名单。
 */
function resolveSafeReturnTo(returnTo, publicBase) {
  const value = String(returnTo || '/').trim();
  if (!value || /[\u0000-\u001f\u007f\\]/.test(value)) {
    throw new CasError('returnTo 不合法', 400, 'CAS_RETURN_TO_INVALID');
  }

  let base;
  try {
    base = new URL(publicBase);
  } catch (_) {
    throw new CasError('本站公开地址配置无效', 503, 'APP_PUBLIC_URL_INVALID');
  }

  if (value.startsWith('/') && !value.startsWith('//')) {
    const target = new URL(value, base);
    if (target.origin !== base.origin) {
      throw new CasError('returnTo 不合法', 400, 'CAS_RETURN_TO_INVALID');
    }
    return target.toString();
  }

  let target;
  try {
    target = new URL(value);
  } catch (_) {
    throw new CasError('returnTo 仅允许本站相对路径', 400, 'CAS_RETURN_TO_INVALID');
  }
  if (!['http:', 'https:'].includes(target.protocol) || !configuredReturnToOrigins().has(target.origin)) {
    throw new CasError('returnTo 外域未在白名单中', 400, 'CAS_RETURN_TO_NOT_ALLOWED');
  }
  return target.toString();
}

module.exports = { CasError, validateCasTicket, buildCasLoginUrl, resolveSafeReturnTo };
