/**
 * 短信触达适配器（商业化触达脚手架）。
 * 未配置时所有调用静默跳过，绝不影响主流程；配置 .env 后即真实发送。
 *
 * 支持两种провайдер（按 SMS_PROVIDER 切换）：
 *   - aliyun  阿里云短信
 *   - tencent 腾讯云短信
 * 通用 .env：
 *   SMS_PROVIDER=aliyun|tencent
 *   SMS_ACCESS_KEY=...        访问密钥 ID
 *   SMS_ACCESS_SECRET=...     访问密钥 Secret
 *   SMS_SIGN_NAME=湖南石化职院  短信签名
 *   SMS_TEMPLATE_CODE=SMS_xxx 模板 CODE（模板含一个 ${content} 变量）
 *
 * 注：真实签名/调用各云有差异，这里给出统一入口与占位实现，
 *     上线时在 sendViaAliyun/sendViaTencent 内接入对应 SDK 即可。
 */
const pool = require('../config/db');

const PROVIDER = process.env.SMS_PROVIDER;
const ACCESS_KEY = process.env.SMS_ACCESS_KEY;
const ACCESS_SECRET = process.env.SMS_ACCESS_SECRET;
const SIGN_NAME = process.env.SMS_SIGN_NAME;
const TEMPLATE_CODE = process.env.SMS_TEMPLATE_CODE;

function configured() {
  return !!(PROVIDER && ACCESS_KEY && ACCESS_SECRET && SIGN_NAME && TEMPLATE_CODE);
}

async function getPhone(userId) {
  try {
    const [rows] = await pool.query('SELECT phone FROM t_user WHERE id = ? LIMIT 1', [userId]);
    return rows[0] && rows[0].phone;
  } catch (_) { return null; }
}

// —— 各云占位实现：接入 SDK 后替换内部逻辑即可 ——
async function sendViaAliyun(phone, content) {
  // TODO: 接入 @alicloud/dysmsapi20170525，使用 SIGN_NAME + TEMPLATE_CODE 发送
  console.log(`[SMS:aliyun] -> ${phone}: ${content}`);
  return true;
}
async function sendViaTencent(phone, content) {
  // TODO: 接入 tencentcloud-sdk-nodejs sms 客户端
  console.log(`[SMS:tencent] -> ${phone}: ${content}`);
  return true;
}

/** 直接给手机号发送（fire-and-forget，失败仅记录）。 */
async function sendToPhone(phone, content) {
  if (!configured() || !phone) return false;
  try {
    if (PROVIDER === 'tencent') return await sendViaTencent(phone, content);
    return await sendViaAliyun(phone, content);
  } catch (e) {
    console.warn('短信发送失败:', e.message);
    return false;
  }
}

/** 给用户发送（按 userId 取手机号）。未配置或无手机号则静默跳过。 */
async function sendToUser(userId, content) {
  if (!configured() || !userId) return false;
  const phone = await getPhone(userId);
  if (!phone) return false;
  return sendToPhone(phone, content);
}

module.exports = { configured, sendToUser, sendToPhone, status: () => ({
  configured: configured(),
  provider: PROVIDER || '',
  signName: SIGN_NAME || ''
}) };
