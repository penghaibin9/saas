/**
 * 国密算法适配（SM3 加盐哈希）——信创/等保合规可选项
 * sm-crypto 懒加载；未安装则在 sm3 模式下抛错（由 password.js 兜底回退）。
 * 哈希格式：$sm3$<saltHex>$<digestHex>，digest = SM3(saltHex + plain)
 */
const crypto = require('crypto');

function sm3Available() {
  try { require('sm-crypto'); return true; } catch { return false; }
}

function sm3Hex(input) {
  const { sm3 } = require('sm-crypto');
  return sm3(input);
}

function hash(plain) {
  const salt = crypto.randomBytes(8).toString('hex');
  const digest = sm3Hex(salt + String(plain));
  return `$sm3$${salt}$${digest}`;
}

function verify(plain, stored) {
  if (typeof stored !== 'string' || !stored.startsWith('$sm3$')) return false;
  const parts = stored.split('$'); // ['', 'sm3', salt, digest]
  const salt = parts[2], digest = parts[3];
  if (!salt || !digest) return false;
  return sm3Hex(salt + String(plain)) === digest;
}

module.exports = { hash, verify, sm3Available, sm3Hex };
