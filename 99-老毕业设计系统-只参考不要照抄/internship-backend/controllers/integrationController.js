const { systemConfigModel } = require('../models');
const { success, error } = require('../utils/response');
const { createToken, ROLE_MAP } = require('../middlewares/auth');
const { userModel } = require('../models');
const { CasError, validateCasTicket, buildCasLoginUrl, resolveSafeReturnTo } = require('../utils/cas');
const wxMessage = require('../utils/wxMessage');
const sms = require('../utils/sms');

function resolvePublicBase(req, cfg) {
  const fromCfg = (cfg.app_public_url || '').replace(/\/$/, '');
  if (fromCfg) return fromCfg;
  const proto = req.get('x-forwarded-proto') || req.protocol || 'http';
  const host = req.get('x-forwarded-host') || req.get('host');
  return `${proto}://${host}`;
}

function resolveCasUrls(cfg) {
  const server = (cfg.cas_server_url || '').replace(/\/$/, '');
  const loginUrl = cfg.cas_login_url || (server ? `${server}/login` : '');
  const validateUrl = cfg.cas_validate_url || (server ? `${server}/serviceValidate` : '');
  return { loginUrl, validateUrl };
}

function userPayload(user) {
  return {
    id: user.id, username: user.username, realName: user.real_name,
    role: user.role, roleName: ROLE_MAP[user.role], collegeId: user.college_id
  };
}

function casErrorResponse(res, err, fallbackMessage) {
  if (err instanceof CasError) {
    return error(res, err.message, err.status, { code: err.code });
  }
  return error(res, fallbackMessage, 500);
}

/** 对接集成：统一认证、Webhook、通道状态 */
const integrationController = {
  async info(req, res) {
    try {
      const cfg = await systemConfigModel.getAll();
      const { loginUrl, validateUrl } = resolveCasUrls(cfg);
      return success(res, {
        casEnabled: cfg.cas_enabled === '1',
        casLoginUrl: loginUrl,
        casValidateUrl: validateUrl,
        casRealMode: !!(validateUrl && cfg.cas_enabled === '1'),
        webhookUrl: cfg.webhook_url || '',
        provinceApiMode: cfg.province_api_mode || 'mock',
        channels: {
          wx: { configured: wxMessage.configured(), enabled: cfg.notify_wx_enabled === '1' },
          sms: { configured: sms.configured(), enabled: cfg.notify_sms_enabled === '1', provider: process.env.SMS_PROVIDER || '' }
        },
        exportEndpoints: [
          { name: '学生档案', path: '/api/export/users?role=4' },
          { name: '教师档案', path: '/api/export/users?role=3' },
          { name: '实习备案包', path: '/api/filings/export' },
          { name: '实习质量报告', path: '/api/quality-report/export' }
        ]
      }, '获取对接信息成功');
    } catch (err) {
      return error(res, '获取对接信息失败：' + err.message, 500);
    }
  },

  /** 跳转 CAS 登录（浏览器重定向） */
  async casRedirect(req, res) {
    try {
      const cfg = await systemConfigModel.getAll();
      if (cfg.cas_enabled !== '1') return error(res, '统一认证未启用', 403);
      const { loginUrl, validateUrl } = resolveCasUrls(cfg);
      if (!loginUrl) return error(res, 'CAS 已启用但未配置登录地址', 503, { code: 'CAS_LOGIN_URL_MISSING' });
      if (!validateUrl) return error(res, 'CAS 已启用但未配置校验地址', 503, { code: 'CAS_VALIDATE_URL_MISSING' });

      const base = resolvePublicBase(req, cfg);
      const returnTo = (req.query.returnTo || '/').toString();
      resolveSafeReturnTo(returnTo, base);
      const service = `${base}/api/integration/cas/callback?returnTo=${encodeURIComponent(returnTo)}`;
      const url = buildCasLoginUrl(loginUrl, service);
      return res.redirect(url);
    } catch (err) {
      return casErrorResponse(res, err, 'CAS 登录跳转失败');
    }
  },

  /** CAS 回调：校验 ticket 后重定向回前端并携带 token */
  async casCallback(req, res) {
    try {
      const cfg = await systemConfigModel.getAll();
      if (cfg.cas_enabled !== '1') return error(res, '统一认证未启用', 403);
      const ticket = req.query.ticket;
      if (!ticket) return error(res, '缺少 CAS ticket', 400);

      const { validateUrl } = resolveCasUrls(cfg);
      if (!validateUrl) return error(res, 'CAS 已启用但未配置校验地址', 503, { code: 'CAS_VALIDATE_URL_MISSING' });
      const base = resolvePublicBase(req, cfg);
      const returnTo = (req.query.returnTo || '/').toString();
      const front = resolveSafeReturnTo(returnTo, base);
      const service = `${base}/api/integration/cas/callback?returnTo=${encodeURIComponent(returnTo)}`;

      const casUser = await validateCasTicket(validateUrl, service, ticket);

      const user = await userModel.findByCasIdentity(casUser);
      if (!user || user.status !== 1) {
        return res.redirect(`${front.split('#')[0]}#cas_error=${encodeURIComponent('用户未开通或已禁用')}`);
      }

      const token = createToken(user);
      const u = encodeURIComponent(JSON.stringify(userPayload(user)));
      const dest = front.split('#')[0] + `#token=${encodeURIComponent(token)}&user=${u}`;
      return res.redirect(dest);
    } catch (err) {
      if (err instanceof CasError && err.code.startsWith('CAS_RETURN_TO')) {
        return casErrorResponse(res, err, 'CAS 回跳地址不合法');
      }
      // 错误兜底不再二次读取配置，避免数据库故障时 catch 内再次抛错；仅回本站根路径。
      const base = resolvePublicBase(req, {});
      const front = resolveSafeReturnTo('/', base);
      const publicMessage = err instanceof CasError ? err.message : '统一认证暂不可用，请稍后重试';
      return res.redirect(`${front.split('#')[0]}#cas_error=${encodeURIComponent(publicMessage)}`);
    }
  },

  /** CAS ticket 换取本系统 token；身份只能来自 CAS 校验结果 */
  async casLogin(req, res) {
    try {
      const cfg = await systemConfigModel.getAll();
      if (cfg.cas_enabled !== '1') return error(res, '统一认证未启用', 403);
      const { ticket } = req.body || {};
      if (!ticket) return error(res, '缺少 CAS ticket', 400, { code: 'CAS_TICKET_MISSING' });

      const { validateUrl } = resolveCasUrls(cfg);
      if (!validateUrl) return error(res, 'CAS 已启用但未配置校验地址', 503, { code: 'CAS_VALIDATE_URL_MISSING' });
      const service = `${resolvePublicBase(req, cfg)}/api/integration/cas/callback`;
      const casUser = await validateCasTicket(validateUrl, service, ticket);

      const user = await userModel.findByCasIdentity(casUser);
      if (!user || user.status !== 1) return error(res, '用户不存在或已禁用：' + casUser, 401);
      const token = createToken(user);
      return success(res, {
        token,
        user: userPayload(user),
        casUser
      }, '统一认证登录成功');
    } catch (err) {
      return casErrorResponse(res, err, '统一认证失败');
    }
  },

  async testWebhook(req, res) {
    try {
      const url = (req.body && req.body.url) || await systemConfigModel.get('webhook_url');
      if (!url) return error(res, '未配置 Webhook 地址', 400);
      const payload = {
        event: 'system.test',
        timestamp: new Date().toISOString(),
        school: await systemConfigModel.get('school_name'),
        message: '实习管理平台 Webhook 连通性测试'
      };
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      return success(res, { status: r.status, ok: r.ok }, r.ok ? 'Webhook 测试成功' : `Webhook 返回 HTTP ${r.status}`);
    } catch (err) {
      return error(res, 'Webhook 测试失败：' + err.message, 500);
    }
  }
};

module.exports = integrationController;
