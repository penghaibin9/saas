/**
 * 个人信息脱敏工具（PIPL / 数据最小化）
 *
 * 用于在"非必要展示全量"的场景对 PII 做掩码，降低泄露面。
 * 注意：官方导出（学信网监管数据等）需要真实数据，不应脱敏；
 *       脱敏只用于列表浏览、跨角色查看等非权威场景。
 */

/** 手机号：保留前3后4 —— 138****8000 */
function maskPhone(v) {
  const s = String(v || '');
  if (!/^\d{7,}$/.test(s)) return v || '';
  return s.replace(/(\d{3})\d+(\d{4})/, '$1****$2');
}

/** 身份证：保留前3后4 */
function maskIdCard(v) {
  const s = String(v || '');
  if (s.length < 8) return v || '';
  return s.slice(0, 3) + '*'.repeat(Math.max(4, s.length - 7)) + s.slice(-4);
}

/** 姓名：保留姓，其余以 * 代替 —— 张** */
function maskName(v) {
  const s = String(v || '');
  if (s.length <= 1) return s;
  return s[0] + '*'.repeat(s.length - 1);
}

/** 学号/工号：保留前2后2 */
function maskEeid(v) {
  const s = String(v || '');
  if (s.length <= 4) return s;
  return s.slice(0, 2) + '*'.repeat(s.length - 4) + s.slice(-2);
}

/** 邮箱：保留首字符与域名 —— a***@x.com */
function maskEmail(v) {
  const s = String(v || '');
  const at = s.indexOf('@');
  if (at <= 0) return v || '';
  return s[0] + '***' + s.slice(at);
}

/**
 * 按字段映射对一行/一组对象脱敏。
 * @param {object|object[]} data
 * @param {object} fieldMap 形如 { phone: 'phone', real_name: 'name', eeid: 'eeid', email: 'email', id_card: 'idcard' }
 *        value 取值：phone|name|eeid|email|idcard
 */
const MASKERS = { phone: maskPhone, name: maskName, eeid: maskEeid, email: maskEmail, idcard: maskIdCard };
function maskObject(data, fieldMap) {
  if (Array.isArray(data)) return data.map(d => maskObject(d, fieldMap));
  if (!data || typeof data !== 'object') return data;
  const out = { ...data };
  for (const [field, kind] of Object.entries(fieldMap)) {
    if (out[field] != null && MASKERS[kind]) out[field] = MASKERS[kind](out[field]);
  }
  return out;
}

/**
 * 自由文本脱敏：掩码文本中夹带的手机号/身份证/邮箱。
 * 用于把学生自填文本送往第三方（如 AI 模型）前，避免 PII 外发。
 */
function scrubText(v) {
  let s = String(v == null ? '' : v);
  // 身份证（18位，含末位X）
  s = s.replace(/\b(\d{6})\d{8}(\d{3}[\dXx])\b/g, '$1********$2');
  // 邮箱
  s = s.replace(/([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/g, '$1***$2');
  // 手机号（11位，1开头），避免命中已被处理的身份证片段
  s = s.replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, (m) => m.slice(0, 3) + '****' + m.slice(-4));
  return s;
}

module.exports = { maskPhone, maskIdCard, maskName, maskEeid, maskEmail, maskObject, scrubText };
