const { notificationModel, systemConfigModel } = require('../models');
const wxMessage = require('./wxMessage');
const sms = require('./sms');
const email = require('./email');
const groupWebhook = require('./groupWebhook');

let _cfgCache = null;
let _cfgAt = 0;
async function channelFlags() {
  if (_cfgCache && Date.now() - _cfgAt < 60000) return _cfgCache;
  try {
    const c = await systemConfigModel.getAll();
    _cfgCache = { wx: c.notify_wx_enabled === '1', sms: c.notify_sms_enabled === '1', email: c.notify_email_enabled === '1' };
  } catch {
    _cfgCache = { wx: true, sms: false, email: false };
  }
  _cfgAt = Date.now();
  return _cfgCache;
}

/**
 * 多渠道通知触达：站内信 + 微信订阅消息 +（可选）短信。
 * 失败仅记录日志，绝不影响主业务流程。
 * @param {object} options - { sms: true } 时额外尝试短信；{ webhook: true } 时额外推送企业微信/钉钉群（未配置则静默跳过）
 */
async function notify(userId, title, content, type = 'info', options = {}) {
  if (!userId) return;
  try {
    await notificationModel.create({ user_id: userId, title, content, type });
    // 实时下发到该用户在线的 SSE 连接（不在线则无副作用）
    try { require('./sse').pushToUser(userId, 'notification', { title, content, type, time: Date.now() }); } catch (_) {}
  } catch (e) {
    console.error('站内通知发送失败:', e.message);
  }
  const ch = await channelFlags();
  if (ch.wx) wxMessage.pushToUser(userId, title, content);
  if (options.sms && ch.sms) {
    sms.sendToUser(userId, `【${title}】${content}`).catch((e) => console.warn('短信触达失败:', e.message));
  }
  if (options.email && ch.email) {
    email.sendToUser(userId, title, content).catch((e) => console.warn('邮件触达失败:', e.message));
  }
  if (options.webhook && groupWebhook.isConfigured()) {
    groupWebhook.push(title, content).catch((e) => console.warn('群机器人触达失败:', e.message));
  }
}

/** 仅向群机器人广播（不落库,用于面向群体的提醒,如"今日 N 人未打卡"） */
async function notifyGroup(title, content) {
  if (groupWebhook.isConfigured()) {
    await groupWebhook.push(title, content).catch((e) => console.warn('群机器人广播失败:', e.message));
  }
}

module.exports = { notify, notifyGroup, channelFlags };
