/**
 * 认证/鉴权守卫单元测试（不依赖数据库）
 * 覆盖：JWT 签发与校验、角色守卫 requireRole、强制改密守卫 requirePasswordChanged
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
process.env.JWT_SECRET = 'unit-test-secret-key-at-least-32-chars-long';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createToken, authMiddleware, requireRole, requirePasswordChanged } = require('../middlewares/auth');

// 构造一个最小可用的 mock res：捕获 status 与 json
function mockRes() {
  return {
    statusCode: 200,
    body: null,
    status(code) { this.statusCode = code; return this; },
    json(obj) { this.body = obj; return this; },
  };
}

test('createToken + authMiddleware：有效令牌可通过并还原身份', () => {
  const token = createToken({ id: 7, username: 'stu1', role: 4, real_name: '学生甲' });
  const req = { headers: { authorization: 'Bearer ' + token } };
  const res = mockRes();
  let passed = false;
  authMiddleware(req, res, () => { passed = true; });
  assert.equal(passed, true);
  assert.equal(req.user.id, 7);
  assert.equal(req.user.role, 4);
});

test('authMiddleware：缺失令牌返回 401', () => {
  const req = { headers: {} };
  const res = mockRes();
  authMiddleware(req, res, () => assert.fail('不应放行'));
  assert.equal(res.statusCode, 401);
});

test('authMiddleware：被篡改的令牌返回 401', () => {
  const req = { headers: { authorization: 'Bearer abc.def.ghi' } };
  const res = mockRes();
  authMiddleware(req, res, () => assert.fail('不应放行'));
  assert.equal(res.statusCode, 401);
});

test('requireRole：角色匹配放行、不匹配 403', () => {
  const allowAdmin = requireRole(1);
  const ok = mockRes();
  let passed = false;
  allowAdmin({ user: { role: 1 } }, ok, () => { passed = true; });
  assert.equal(passed, true);

  const denied = mockRes();
  allowAdmin({ user: { role: 4 } }, denied, () => assert.fail('学生不应进入管理员接口'));
  assert.equal(denied.statusCode, 403);
});

test('requireRole：未登录返回 401', () => {
  const guard = requireRole(1, 2);
  const res = mockRes();
  guard({}, res, () => assert.fail('不应放行'));
  assert.equal(res.statusCode, 401);
});

test('requirePasswordChanged：未改密被拦截 403/MUST_CHANGE_PASSWORD', () => {
  const res = mockRes();
  requirePasswordChanged({ user: { id: 1, mustChangePassword: true } }, res, () => assert.fail('应被拦截'));
  assert.equal(res.statusCode, 403);
  assert.equal(res.body.data.code, 'MUST_CHANGE_PASSWORD');
});

test('requirePasswordChanged：已改密放行', () => {
  const res = mockRes();
  let passed = false;
  requirePasswordChanged({ user: { id: 1, mustChangePassword: false } }, res, () => { passed = true; });
  assert.equal(passed, true);
});
