/**
 * 商业化波次纯逻辑测试（不依赖数据库）
 * 覆盖：实习报酬 80% 合规判定、报送字段映射。
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const stipendModel = require('../models/stipendModel');
const reportingModel = require('../models/reportingModel');

test('报酬合规：达到试用期工资80%判定为合规', () => {
  assert.equal(stipendModel.compliant(1600, 2000), true);  // 80% 临界
  assert.equal(stipendModel.compliant(1599, 2000), false); // 低于80%
  assert.equal(stipendModel.compliant(3000, 2000), true);
});

test('报酬合规：无参考工资返回 null（待核，不武断判违规）', () => {
  assert.equal(stipendModel.compliant(1000, null), null);
  assert.equal(stipendModel.compliant(1000, 0), null);
  assert.equal(stipendModel.compliant(1000, undefined), null);
});

test('报送字段映射：fieldMap 含核心列', () => {
  const labels = reportingModel.fieldMap().map((f) => f.label);
  for (const need of ['学号', '姓名', '实习单位', '实习开始', '实习结束']) {
    assert.ok(labels.includes(need), '缺少列：' + need);
  }
});

test('报送标准行：按标准列名映射，缺失字段补空串', () => {
  const rows = reportingModel.toStandardRows([
    { eeid: '2024001', student_name: '张三', enterprise_name: '某公司' },
  ]);
  assert.equal(rows[0]['学号'], '2024001');
  assert.equal(rows[0]['姓名'], '张三');
  assert.equal(rows[0]['实习单位'], '某公司');
  assert.equal(rows[0]['指导教师'], ''); // 未提供 → 空串而非 undefined
});
