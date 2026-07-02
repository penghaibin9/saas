/**
 * 口令哈希适配层测试（默认 bcrypt；国密 SM3 为可选依赖，按前缀自动识别）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
delete process.env.PASSWORD_ALGO; // 默认 bcrypt
const { test } = require('node:test');
const assert = require('node:assert/strict');
const pwd = require('../utils/password');
const gm = require('../utils/gmcrypt');

test('bcrypt：哈希后可校验，错误口令拒绝', async () => {
  const h = await pwd.hash('abc123');
  assert.ok(h.startsWith('$2'), 'bcrypt 哈希应以 $2 开头');
  assert.equal(await pwd.compare('abc123', h), true);
  assert.equal(await pwd.compare('wrong', h), false);
});

test('compare：按前缀识别——非 $sm3$ 的输入不会误判', async () => {
  // 传入一个非 sm3 的伪哈希，应走 bcrypt 分支且安全返回 false（不抛错）
  assert.equal(await pwd.compare('x', '$2a$10$invalidinvalidinvalidinvalidinv'), false);
});

test('gmcrypt：verify 对非 sm3 字符串返回 false（无需 sm-crypto 依赖）', () => {
  assert.equal(gm.verify('x', 'not-an-sm3-hash'), false);
  assert.equal(gm.verify('x', '$2a$10$whatever'), false);
});

// 仅在安装了可选依赖 sm-crypto 时验证国密往返
test('国密 SM3：哈希往返（仅当安装 sm-crypto 时）', { skip: !gm.sm3Available() }, () => {
  const h = gm.hash('abc123');
  assert.ok(h.startsWith('$sm3$'));
  assert.equal(gm.verify('abc123', h), true);
  assert.equal(gm.verify('wrong', h), false);
});
