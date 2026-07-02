/**
 * 打卡反作弊评估单元测试（纯逻辑，不依赖数据库/外网）
 * 运行：npm run test:unit
 */
process.env.NODE_ENV = 'test';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const risk = require('../utils/checkinRisk');

test('正常打卡：无风险', () => {
  const r = risk.assess({ lat: 28.2, lng: 112.9, accuracy: 20, isMock: false }, null);
  assert.equal(r.level, 'none');
  assert.equal(r.reasons.length, 0);
});

test('模拟定位：高风险', () => {
  const r = risk.assess({ lat: 28.2, lng: 112.9, accuracy: 20, isMock: true }, null);
  assert.equal(r.level, 'high');
  assert.ok(r.reasons.some((x) => x.includes('模拟定位')));
});

test('定位精度异常：中风险', () => {
  const r = risk.assess({ lat: 28.2, lng: 112.9, accuracy: 5000, isMock: false }, null);
  assert.equal(r.level, 'medium');
  assert.ok(r.reasons.some((x) => x.includes('精度异常')));
});

test('位移突变：高风险（短时间跨城）', () => {
  const last = { lat: 28.2, lng: 112.9, time: new Date(Date.now() - 5 * 60 * 1000) }; // 5分钟前在长沙
  const r = risk.assess({ lat: 39.9, lng: 116.4, accuracy: 20, isMock: false }, last); // 现在在北京
  assert.equal(r.level, 'high');
  assert.ok(r.reasons.some((x) => x.includes('位移突变')));
  assert.ok(r.speedKmh > 250);
});

test('合理通勤移动：不报位移突变', () => {
  const last = { lat: 28.2000, lng: 112.9000, time: new Date(Date.now() - 60 * 60 * 1000) }; // 1小时前
  const r = risk.assess({ lat: 28.2100, lng: 112.9100, accuracy: 20, isMock: false }, last); // 约1.5km
  assert.equal(r.level, 'none');
});

test('mock 兼容字符串 "1" 与数字 1', () => {
  assert.equal(risk.assess({ isMock: '1' }, null).level, 'high');
  assert.equal(risk.assess({ isMock: 1 }, null).level, 'high');
});
