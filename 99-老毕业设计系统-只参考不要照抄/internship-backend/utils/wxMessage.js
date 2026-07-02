/**
 * 微信订阅消息发送（商业化触达脚手架）。
 * 运营方只需在 .env 配置以下变量即可启用，未配置时所有调用静默跳过，绝不影响主流程：
 *   WX_MP_APPID         小程序 AppID
 *   WX_MP_SECRET        小程序 AppSecret
 *   WX_TEMPLATE_NOTIFY  订阅消息模板ID（通用通知）
 * 说明：订阅消息需用户在小程序侧调用 wx.requestSubscribeMessage 授权，且后端已存有 openid。
 */
const pool = require('../config/db');

const APPID = process.env.WX_MP_APPID;
const SECRET = process.env.WX_MP_SECRET;
const TEMPLATE_NOTIFY = process.env.WX_TEMPLATE_NOTIFY;

let _token = { value: null, exp: 0 };

function configured() { return !!(APPID && SECRET && TEMPLATE_NOTIFY); }

async function getAccessToken() {
  if (_token.value && _token.exp > Date.now()) return _token.value;
  const url = `https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=${APPID}&secret=${SECRET}`;
  const res = await fetch(url);
  const j = await res.json();
  if (!j.access_token) throw new Error('获取微信 access_token 失败：' + (j.errmsg || ''));
  _token = { value: j.access_token, exp: Date.now() + (j.expires_in - 300) * 1000 };
  return _token.value;
}

async function getOpenid(userId) {
  try {
    const [rows] = await pool.query('SELECT wx_openid FROM t_user WHERE id = ? LIMIT 1', [userId]);
    return rows[0] && rows[0].wx_openid;
  } catch (_) { return null; }
}

// code2session：小程序 wx.login 的 code 换取 openid（需配置 AppID/Secret）
async function code2session(code) {
  if (!APPID || !SECRET) throw new Error('未配置微信小程序 AppID/Secret');
  const url = `https://api.weixin.qq.com/sns/jscode2session?appid=${APPID}&secret=${SECRET}&js_code=${code}&grant_type=authorization_code`;
  const res = await fetch(url);
  const j = await res.json();
  if (!j.openid) throw new Error('换取 openid 失败：' + (j.errmsg || ''));
  return { openid: j.openid, unionid: j.unionid };
}

/**
 * 给用户推送订阅消息（fire-and-forget，失败仅记录）。
 * data 形如 { thing1:{value}, ... } 取决于模板字段；此处提供通用 title/content 适配。
 */
async function pushToUser(userId, title, content) {
  if (!configured()) return; // 未启用直接跳过
  try {
    const openid = await getOpenid(userId);
    if (!openid) return;
    const token = await getAccessToken();
    const body = {
      touser: openid,
      template_id: TEMPLATE_NOTIFY,
      page: 'pages/notifications/notifications',
      data: {
        thing1: { value: String(title).slice(0, 20) },
        thing2: { value: String(content).slice(0, 20) }
      }
    };
    const res = await fetch(`https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token=${token}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    });
    const j = await res.json();
    if (j.errcode && j.errcode !== 0) console.warn('订阅消息发送返回:', j.errcode, j.errmsg);
  } catch (e) {
    console.warn('订阅消息发送失败:', e.message);
  }
}

module.exports = { configured, pushToUser, code2session, getOpenid, status: () => ({
  configured: configured(),
  appId: APPID ? APPID.slice(0, 6) + '…' : ''
}) };
