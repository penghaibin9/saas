const crypto = require('crypto');
const pwdHash = require('../utils/password');
const dayjs = require('dayjs');
const { userModel } = require('../models');
const { createToken, ROLE_MAP } = require('../middlewares/auth');
const { success, error } = require('../utils/response');
const wxMessage = require('../utils/wxMessage');

/**
 * 微信扫码登录（模拟实现）：
 * 因无真实微信开放平台 appid/secret，此处用内存票据模拟完整扫码登录时序：
 *   1) PC 端请求二维码 -> 生成 ticket(pending)
 *   2) PC 端轮询票据状态
 *   3) 手机端“扫码并确认”(此处用账号密码确认，等价于微信授权回调) -> 票据置 confirmed 并下发令牌
 * 生产接入真实微信时，仅需把 confirm 换成微信 OAuth 回调即可，前端时序不变。
 */
const tickets = new Map();
const TTL = 120 * 1000; // 2 分钟

const cleaner = setInterval(() => {
  const now = Date.now();
  for (const [k, v] of tickets) if (v.expireAt < now) tickets.delete(k);
}, 60 * 1000);
if (typeof cleaner.unref === 'function') cleaner.unref();

function sanitize(u) {
  return {
    id: u.id, username: u.username, realName: u.real_name, role: u.role,
    roleName: ROLE_MAP[u.role] || '', collegeId: u.college_id,
    lastLoginTime: u.last_login_time ? dayjs(u.last_login_time).format('YYYY-MM-DD HH:mm:ss') : null
  };
}

const wechatController = {
  // 1) 生成登录二维码票据
  createQr(req, res) {
    const ticket = crypto.randomBytes(16).toString('hex');
    tickets.set(ticket, { status: 'pending', expireAt: Date.now() + TTL });
    return success(res, {
      ticket,
      qrContent: 'wxlogin://' + ticket,
      expiresIn: TTL / 1000,
      isDemo: true,
      mode: 'password-confirmation'
    }, '演示二维码已生成（非微信身份认证）');
  },

  // 2) 轮询票据状态
  poll(req, res) {
    const t = tickets.get(req.params.ticket);
    if (!t || t.expireAt < Date.now()) { tickets.delete(req.params.ticket); return success(res, { status: 'expired', isDemo: true }, 'ok'); }
    if (t.status === 'confirmed') {
      const payload = { status: 'confirmed', token: t.token, user: t.user, mustChangePassword: t.mustChangePassword, isDemo: true };
      tickets.delete(req.params.ticket); // 一次性消费
      return success(res, payload, '登录成功');
    }
    return success(res, { status: t.status, isDemo: true }, 'ok');
  },

  // 3) 手机端扫码确认（模拟微信授权）：用账号密码确认身份并绑定票据
  async confirm(req, res) {
    try {
      const t = tickets.get(req.params.ticket);
      if (!t || t.expireAt < Date.now()) return error(res, '二维码已失效，请刷新', 400);

      const { username, password } = req.body;
      if (!username || !password) return error(res, '请输入账号密码完成确认', 400);
      const user = await userModel.findByUsername(username);
      if (!user) return error(res, '账号或密码错误', 401);
      if (user.status !== 1) return error(res, '账号已被禁用', 403);
      const ok = await pwdHash.compare(password, user.password);
      if (!ok) return error(res, '账号或密码错误', 401);

      t.status = 'confirmed';
      t.token = createToken(user);
      t.user = sanitize(user);
      t.mustChangePassword = Boolean(user.must_change_password);
      await userModel.updateLastLoginTime(user.id);
      return success(res, { isDemo: true, mode: 'password-confirmation' }, '演示确认完成，请在电脑端继续');
    } catch (err) {
      return error(res, '确认失败：' + err.message, 500);
    }
  },

  // 小程序绑定 openid：传 wx.login 拿到的 code，后端 code2session 换取 openid 并绑定到当前登录用户。
  // 需登录（在受保护路由下调用）。未配置 AppID/Secret 时返回提示。
  async bindMpOpenid(req, res) {
    try {
      if (!req.user) return error(res, '请先登录', 401);
      const { code } = req.body;
      if (!code) return error(res, '缺少 code', 400);
      if (!wxMessage.configured && !process.env.WX_MP_APPID) {
        return error(res, '服务端未配置微信小程序凭据，无法绑定', 400);
      }
      const { openid } = await wxMessage.code2session(code);
      await userModel.setOpenid(req.user.id, openid);
      return success(res, null, '微信绑定成功');
    } catch (err) {
      return error(res, '绑定失败：' + err.message, 500);
    }
  }
};

module.exports = wechatController;
