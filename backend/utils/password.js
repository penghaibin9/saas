/**
 * 口令哈希适配层 — 移植自旧系统（去除国密可选依赖，保留 bcrypt）
 * ───────────────────────────────────────────────────────────
 * 默认 bcrypt。校验时按存储哈希前缀识别（$2 → bcrypt），新旧哈希可共存。
 * 如需信创/等保 SM3，可后续接入 utils/gmcrypt（可选依赖 sm-crypto）。
 */
const bcrypt = require('bcryptjs');

const ROUNDS = Number(process.env.BCRYPT_ROUNDS || 10);

async function hash(plain) {
  return bcrypt.hash(String(plain), ROUNDS);
}

async function compare(plain, stored) {
  return bcrypt.compare(String(plain), stored || '');
}

module.exports = { hash, compare, algo: () => 'bcrypt' };
