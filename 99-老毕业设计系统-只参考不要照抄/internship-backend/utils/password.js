/**
 * 口令哈希适配层（可插拔 bcrypt / 国密 SM3）
 * ───────────────────────────────────────────────────────────
 * · 默认 bcrypt（安全且通用）；
 * · PASSWORD_ALGO=sm3 时用国密 SM3 加盐（信创/等保合规），需安装可选依赖 sm-crypto，
 *   未安装则自动回退 bcrypt，不阻断。
 * 校验时按存储哈希前缀自动识别（$sm3$ → SM3；$2 → bcrypt），故新旧哈希可共存、平滑迁移。
 */
const bcrypt = require('bcryptjs');
const gm = require('./gmcrypt');

const ALGO = (process.env.PASSWORD_ALGO || 'bcrypt').toLowerCase();
const ROUNDS = Number(process.env.BCRYPT_ROUNDS || 10);

async function hash(plain) {
  if (ALGO === 'sm3') {
    if (gm.sm3Available()) return gm.hash(plain);
    console.warn('⚠️  PASSWORD_ALGO=sm3 但未安装 sm-crypto，本次回退 bcrypt');
  }
  return bcrypt.hash(String(plain), ROUNDS);
}

async function compare(plain, stored) {
  if (typeof stored === 'string' && stored.startsWith('$sm3$')) {
    return gm.verify(plain, stored);
  }
  return bcrypt.compare(String(plain), stored || '');
}

module.exports = { hash, compare, algo: () => ALGO };
