/**
 * 通用输入校验与分页处理工具
 */

// 中国大陆手机号（11 位，1 开头，第二位 3-9）
function isValidPhone(phone) {
  return /^1[3-9]\d{9}$/.test(String(phone).trim());
}

// 基础邮箱格式
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).trim());
}

// 强密码：至少 6 位，且同时包含字母和数字（需求：初始密码须为数字+字母组合）
function isStrongPassword(pwd) {
  const s = String(pwd);
  return s.length >= 6 && /[a-zA-Z]/.test(s) && /\d/.test(s);
}

/**
 * 解析并夹紧分页参数，避免 NaN/负数/超大 pageSize 进入 SQL。
 * @returns {{ page:number, pageSize:number }}
 */
function clampPagination(query = {}, { defaultPageSize = 20, maxPageSize = 100 } = {}) {
  let page = Number(query.page);
  let pageSize = Number(query.page_size ?? query.pageSize);
  if (!Number.isFinite(page) || page < 1) page = 1;
  if (!Number.isFinite(pageSize) || pageSize < 1) pageSize = defaultPageSize;
  page = Math.floor(page);
  pageSize = Math.min(Math.floor(pageSize), maxPageSize);
  return { page, pageSize };
}

module.exports = { isValidPhone, isValidEmail, isStrongPassword, clampPagination };
