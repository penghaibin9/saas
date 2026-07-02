/**
 * 计费对账 纯逻辑单元测试（用量 vs 配额，不依赖 DB）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { reconcileUsage } = require('../services/billingService');

const QUOTA = { max_students: 2000, max_storage_mb: 51200, ai_monthly_quota: 5000 };

test('reconcileUsage：用量未及配额 → ok', () => {
  const r = reconcileUsage(QUOTA, { students: 1000, storage_mb: 10240, ai_calls: 1000 });
  assert.equal(r.status, 'ok');
  assert.equal(r.overDims.length, 0);
  assert.equal(r.dims.students.pct, 50); // 1000/2000
});

test('reconcileUsage：任一维度≥90% → warn（临界）', () => {
  const r = reconcileUsage(QUOTA, { students: 1900, ai_calls: 100 }); // 学生 95%
  assert.equal(r.status, 'warn');
  assert.equal(r.dims.students.pct, 95);
  assert.equal(r.dims.students.over, false);
});

test('reconcileUsage：超配额 → over，并列出超限维度', () => {
  const r = reconcileUsage(QUOTA, { students: 2100, ai_calls: 6000 });
  assert.equal(r.status, 'over');
  assert.deepEqual(r.overDims.sort(), ['ai', 'students']);
  assert.equal(r.dims.students.over, true);
  assert.equal(r.dims.ai.over, true);
});

test('reconcileUsage：未设配额(0)不判超限，利用率 0', () => {
  const r = reconcileUsage({}, { students: 9999, ai_calls: 9999 });
  assert.equal(r.status, 'ok');
  assert.equal(r.dims.students.pct, 0);
  assert.equal(r.dims.students.over, false);
});
