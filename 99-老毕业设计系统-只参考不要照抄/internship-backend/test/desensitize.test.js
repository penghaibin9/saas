/**
 * 个人信息脱敏单元测试
 * 运行：npm run test:unit
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const d = require('../utils/desensitize');

test('maskPhone：保留前3后4', () => {
  assert.equal(d.maskPhone('13812345678'), '138****5678');
  assert.equal(d.maskPhone(''), '');
  assert.equal(d.maskPhone('abc'), 'abc'); // 非手机号原样返回
});

test('maskName：保留姓', () => {
  assert.equal(d.maskName('张三'), '张*');
  assert.equal(d.maskName('欧阳娜娜'), '欧***');
  assert.equal(d.maskName('李'), '李');
});

test('maskEeid：保留前2后2', () => {
  assert.equal(d.maskEeid('20240001'), '20****01');
  assert.equal(d.maskEeid('1234'), '1234'); // 太短不脱敏
});

test('maskEmail：保留首字符与域名', () => {
  assert.equal(d.maskEmail('alice@x.com'), 'a***@x.com');
  assert.equal(d.maskEmail('notanemail'), 'notanemail');
});

test('maskObject：批量按字段映射脱敏，不改其他字段', () => {
  const rows = [{ real_name: '张三', phone: '13812345678', eeid: '20240001', age: 20 }];
  const out = d.maskObject(rows, { real_name: 'name', phone: 'phone', eeid: 'eeid' });
  assert.equal(out[0].real_name, '张*');
  assert.equal(out[0].phone, '138****5678');
  assert.equal(out[0].eeid, '20****01');
  assert.equal(out[0].age, 20); // 未映射字段保持不变
  // 不修改原对象
  assert.equal(rows[0].real_name, '张三');
});

test('scrubText：掩码自由文本中的手机号/身份证/邮箱（发AI前防PII外发）', () => {
  assert.equal(d.scrubText('联系我13812345678谢谢'), '联系我138****5678谢谢');
  assert.equal(d.scrubText('邮箱alice@x.com'), '邮箱a***@x.com');
  const idOut = d.scrubText('身份证110101199001011234');
  assert.ok(idOut.includes('110101') && idOut.includes('234') && idOut.includes('*'));
  assert.equal(d.scrubText('本周完成数据库设计，无敏感信息'), '本周完成数据库设计，无敏感信息'); // 无PII不变
});
