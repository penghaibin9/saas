/**
 * SaaS 平台运营 + 多租户内核 单元测试（不依赖 multi 库，single 模式可跑）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
delete process.env.TENANCY_MODE; // 默认 single

const { test } = require('node:test');
const assert = require('node:assert/strict');
const tenancy = require('../config/tenancy');
const tenantModel = require('../models/tenantModel');
const { studentQuotaExceeded } = require('../utils/tenantQuota');
const { AppErr } = require('../services/platformService');

test('forEachTenant：single 模式仅默认租户执行一次', async () => {
  let calls = 0;
  const results = await tenancy.forEachTenant(() => { calls++; return 'done'; });
  assert.equal(calls, 1);
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, true);
  assert.equal(results[0].result, 'done');
  assert.equal(results[0].tenant, tenancy.DEFAULT_TENANT_CODE);
});

test('forEachTenant：单租户失败不影响整体（捕获为 ok:false）', async () => {
  const results = await tenancy.forEachTenant(() => { throw new Error('boom'); });
  assert.equal(results[0].ok, false);
  assert.equal(results[0].error, 'boom');
});

test('allActiveTenants：single 模式返回默认租户', async () => {
  const list = await tenancy.allActiveTenants();
  assert.equal(list.length, 1);
  assert.equal(list[0].code, tenancy.DEFAULT_TENANT_CODE);
});

test('studentQuotaExceeded：single 模式永远不限（false）', async () => {
  assert.equal(await studentQuotaExceeded(), false);
});

test('poolStats：返回连接池治理参数', () => {
  const s = tenancy.poolStats();
  assert.ok(typeof s.cached === 'number');
  assert.ok(typeof s.connectionLimit === 'number');
  assert.ok(typeof s.idleMs === 'number');
});

test('默认套餐齐备（trial/standard/pro，配额递增）', () => {
  const codes = tenantModel.DEFAULT_PLANS.map((p) => p.code);
  assert.deepEqual(codes, ['trial', 'standard', 'pro']);
  const [t, s, p] = tenantModel.DEFAULT_PLANS;
  assert.ok(t.max_students < s.max_students && s.max_students < p.max_students);
  assert.ok(t.ai_monthly_quota < p.ai_monthly_quota);
});

test('AppErr：带 HTTP 状态的平台异常', () => {
  const e = new AppErr('x', 409);
  assert.equal(e.status, 409);
  assert.equal(e.isAppError, true);
});
