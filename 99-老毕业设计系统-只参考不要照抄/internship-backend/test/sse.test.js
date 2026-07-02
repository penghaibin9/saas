/**
 * SSE 多租户隔离 + 本地推送 单元测试（不依赖 Redis/HTTP）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
delete process.env.REDIS_URL; // 确保走本地推送分支
const { test } = require('node:test');
const assert = require('node:assert/strict');
const sse = require('../utils/sse');

// 伪造一个 res：记录写入的 SSE 帧
function fakeRes() {
  const frames = [];
  return { frames, write: (s) => { frames.push(s); return true; } };
}

test('keyOf：按「租户#用户」生成复合键，租户隔离', () => {
  assert.equal(sse.keyOf('schoola', 1), 'schoola#1');
  assert.notEqual(sse.keyOf('schoola', 1), sse.keyOf('schoolb', 1)); // 同号不同校不串
});

test('pushToUser：仅推送给同租户同用户的连接', () => {
  const a = fakeRes(), b = fakeRes();
  sse.addClient(1, a, 'schoola');
  sse.addClient(1, b, 'schoolb'); // 同号、异校

  const n = sse.pushToUser(1, 'notification', { title: 'hi' }, 'schoola');
  assert.equal(n, 1, '应只推给 schoola 的 1 号');
  assert.ok(a.frames.join('').includes('hi'), 'schoola 收到');
  assert.equal(b.frames.join('').includes('hi'), false, 'schoolb 不应收到');

  sse.removeClient(1, a, 'schoola');
  sse.removeClient(1, b, 'schoolb');
  assert.equal(sse.pushToUser(1, 'notification', {}, 'schoola'), 0, '断开后无连接');
});

test('pushToUser：离线用户无副作用（返回 0）', () => {
  assert.equal(sse.pushToUser(999, 'notification', { x: 1 }, 'schoolx'), 0);
});
