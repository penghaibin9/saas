/**
 * 群机器人通知（企业微信 / 钉钉）—— 可插拔
 *
 * 用于把重要节点（待审批、超期催办、风险预警等）推送到教师/管理员的
 * 企业微信群或钉钉群,职院老师更常用群消息,触达率高于站内信。
 *
 * 环境变量（任配其一或都配；未配置则静默跳过）：
 *   WECOM_WEBHOOK     企业微信群机器人 Webhook 地址
 *   DINGTALK_WEBHOOK  钉钉群机器人 Webhook 地址
 *   DINGTALK_KEYWORD  钉钉机器人「自定义关键词」安全设置时,内容需含该词(默认 实习)
 */

function isConfigured() {
  return !!(process.env.WECOM_WEBHOOK || process.env.DINGTALK_WEBHOOK);
}

async function postJson(url, body, timeoutMs = 8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    return res.ok;
  } finally {
    clearTimeout(timer);
  }
}

/** 推送一条文本到已配置的群机器人。fire-and-forget,失败仅记录。 */
async function push(title, content) {
  const text = `${title}\n${content}`;
  const tasks = [];
  if (process.env.WECOM_WEBHOOK) {
    tasks.push(
      postJson(process.env.WECOM_WEBHOOK, { msgtype: 'text', text: { content: text } })
        .catch(e => console.warn('企业微信群推送失败:', e.message))
    );
  }
  if (process.env.DINGTALK_WEBHOOK) {
    const keyword = process.env.DINGTALK_KEYWORD || '实习';
    // 钉钉「自定义关键词」安全模式要求内容包含关键词
    const ddText = text.includes(keyword) ? text : `【${keyword}】${text}`;
    tasks.push(
      postJson(process.env.DINGTALK_WEBHOOK, { msgtype: 'text', text: { content: ddText } })
        .catch(e => console.warn('钉钉群推送失败:', e.message))
    );
  }
  await Promise.all(tasks);
}

module.exports = { push, isConfigured };
