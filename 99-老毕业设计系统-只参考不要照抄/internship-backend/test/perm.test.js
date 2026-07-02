/**
 * 自定义角色/数据权限引擎 纯逻辑测试（不依赖数据库）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const perm = require('../models/permModel');

test('hasPermission：命中/未命中/空要求', () => {
  assert.equal(perm.hasPermission(['user:view', 'intern:view'], 'user:view'), true);
  assert.equal(perm.hasPermission(['user:view'], 'user:manage'), false);
  assert.equal(perm.hasPermission([], 'user:view'), false);
  assert.equal(perm.hasPermission(['user:view'], undefined), true); // 无要求即放行
});

test('widestScope：取最宽数据范围 all>college>class>self', () => {
  assert.equal(perm.widestScope('self', 'college'), 'college');
  assert.equal(perm.widestScope('college', 'all'), 'all');
  assert.equal(perm.widestScope('class', 'self'), 'class');
  assert.equal(perm.widestScope(null, 'college'), 'college');
  assert.equal(perm.widestScope('all', null), 'all');
});

test('scopeToFilter：按数据范围解析过滤条件', () => {
  const user = { id: 7, collegeId: 3, classId: 99 };
  assert.deepEqual(perm.scopeToFilter('all', user), {});
  assert.deepEqual(perm.scopeToFilter('college', user), { collegeId: 3 });
  assert.deepEqual(perm.scopeToFilter('class', user), { classId: 99 });
  assert.deepEqual(perm.scopeToFilter('self', user), { userId: 7 });
  assert.deepEqual(perm.scopeToFilter('unknown', user), { userId: 7 }); // 兜底 self
});

test('权限码目录与范围选项齐备', () => {
  assert.ok(perm.PERMISSIONS.some((p) => p.code === 'perm:admin'));
  assert.deepEqual(perm.SCOPES, ['all', 'college', 'class', 'self']);
});
