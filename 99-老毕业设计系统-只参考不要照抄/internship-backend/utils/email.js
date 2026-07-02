/**
 * 邮件触达适配器（商业化触达脚手架）
 * 与 utils/sms.js 一致：未配置时静默跳过、绝不影响主流程；配置 .env 后即真实发送。
 * nodemailer 采用懒加载，未安装该依赖时自动降级为日志（不阻断）。
 *
 * 环境变量：
 *   EMAIL_HOST      SMTP 主机（如 smtp.exmail.qq.com）
 *   EMAIL_PORT      端口，默认 465
 *   EMAIL_SECURE    是否 SSL，默认 true（465 用 true，587 用 false）
 *   EMAIL_USER      账号
 *   EMAIL_PASS      授权码/密码
 *   EMAIL_FROM      发件人显示，默认与 EMAIL_USER 相同
 */
const pool = require('../config/db');

const HOST = process.env.EMAIL_HOST;
const PORT = Number(process.env.EMAIL_PORT || 465);
const SECURE = process.env.EMAIL_SECURE ? process.env.EMAIL_SECURE === 'true' : true;
const USER = process.env.EMAIL_USER;
const PASS = process.env.EMAIL_PASS;
const FROM = process.env.EMAIL_FROM || USER;

let _transport = null;

function configured() {
  return !!(HOST && USER && PASS);
}

function getTransport() {
  if (!configured()) return null;
  if (_transport) return _transport;
  try {
    const nodemailer = require('nodemailer');
    _transport = nodemailer.createTransport({ host: HOST, port: PORT, secure: SECURE, auth: { user: USER, pass: PASS } });
    return _transport;
  } catch (e) {
    console.warn('⚠️  未安装 nodemailer，邮件功能降级为日志：', e.message);
    return null;
  }
}

async function getEmail(userId) {
  try {
    const [rows] = await pool.query('SELECT email FROM t_user WHERE id = ? LIMIT 1', [userId]);
    return rows[0] && rows[0].email;
  } catch (_) { return null; }
}

/** 给邮箱发送（fire-and-forget，失败仅记录）。未配置或无依赖则静默跳过。 */
async function sendToAddress(to, subject, text) {
  if (!to) return false;
  const t = getTransport();
  if (!t) { console.log(`[EMAIL:demo] -> ${to}: ${subject}`); return false; }
  try {
    await t.sendMail({ from: FROM, to, subject, text });
    return true;
  } catch (e) {
    console.warn('邮件发送失败:', e.message);
    return false;
  }
}

/** 给用户发送（按 userId 取邮箱）。未配置或无邮箱则静默跳过。 */
async function sendToUser(userId, subject, text) {
  if (!configured() || !userId) return false;
  const to = await getEmail(userId);
  if (!to) return false;
  return sendToAddress(to, subject, text);
}

module.exports = {
  configured, sendToUser, sendToAddress,
  status: () => ({ configured: configured(), host: HOST || '', from: FROM || '' }),
};
