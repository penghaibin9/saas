/**
 * 报酬 Service 合规域规则单元测试（纯逻辑，不依赖数据库）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { complianceInfo } = require('../services/stipendService');

test('complianceInfo：达到80%判合规，附比例与标签', () => {
  const ok = complianceInfo(1600, 2000);
  assert.equal(ok.compliant, true);
  assert.equal(ok.ratio, 0.8);
  assert.equal(ok.label, '合规');
});

test('complianceInfo：低于80%判不合规，标签含当前百分比', () => {
  const no = complianceInfo(1400, 2000);
  assert.equal(no.compliant, false);
  assert.ok(no.label.includes('70%'));
});

test('complianceInfo：无参考工资返回待核（null，不武断判违规）', () => {
  const u = complianceInfo(1000, null);
  assert.equal(u.compliant, null);
  assert.equal(u.ratio, null);
  assert.ok(u.label.includes('待核'));
  assert.equal(complianceInfo(1000, 0).compliant, null);
});
