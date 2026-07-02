/**
 * 核心算法单元测试（纯函数，无需数据库）
 * 运行：npm run test:unit
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const benchmarkModel = require('../models/benchmarkModel');

/* ===================== 选题互选匹配 ===================== */

test('planTopicMatches：按优先级录取，单一名额只录第一志愿者', () => {
  const choices = [
    { id: 2, student_id: 20, pool_id: 1, priority: 1 },
    { id: 1, student_id: 10, pool_id: 1, priority: 2 },
  ];
  const winners = benchmarkModel.planTopicMatches(choices, { 1: 1 });
  assert.equal(winners.length, 1);
  assert.equal(winners[0].student_id, 20); // priority 1 胜出
});

test('planTopicMatches：尊重 quota>1，可录取多名', () => {
  const choices = [
    { id: 1, student_id: 10, pool_id: 1, priority: 1 },
    { id: 2, student_id: 20, pool_id: 1, priority: 2 },
    { id: 3, student_id: 30, pool_id: 1, priority: 3 },
  ];
  const winners = benchmarkModel.planTopicMatches(choices, { 1: 2 });
  assert.equal(winners.length, 2);
  assert.deepEqual(winners.map(w => w.student_id), [10, 20]);
});

test('planTopicMatches：同一学生不会被重复录取到多个课题', () => {
  const choices = [
    { id: 1, student_id: 10, pool_id: 1, priority: 1 }, // 录取到 pool 1
    { id: 2, student_id: 10, pool_id: 2, priority: 2 }, // 应被跳过
  ];
  const winners = benchmarkModel.planTopicMatches(choices, { 1: 5, 2: 5 });
  assert.equal(winners.length, 1);
  assert.equal(winners[0].pool_id, 1);
});

test('planTopicMatches：名额用尽后落选，先到先得(同优先级按 id)', () => {
  const choices = [
    { id: 5, student_id: 50, pool_id: 9, priority: 1 },
    { id: 3, student_id: 30, pool_id: 9, priority: 1 },
  ];
  const winners = benchmarkModel.planTopicMatches(choices, { 9: 1 });
  assert.equal(winners.length, 1);
  assert.equal(winners[0].student_id, 30); // 同优先级 id 小者先
});

test('planTopicMatches：空输入与无名额安全返回空', () => {
  assert.deepEqual(benchmarkModel.planTopicMatches([], {}), []);
  assert.deepEqual(
    benchmarkModel.planTopicMatches([{ id: 1, student_id: 1, pool_id: 1, priority: 1 }], { 1: 0 }),
    []
  );
});

/* ===================== 实习综合考评加权 ===================== */

test('scoreInternComponents：四项齐全按权重加权', () => {
  const r = benchmarkModel.scoreInternComponents([
    { key: 'checkin', score: 100, weight: 20 },
    { key: 'log', score: 100, weight: 30 },
    { key: 'enterprise', score: 80, weight: 30 },
    { key: 'school', score: 90, weight: 20 },
  ]);
  // (100*20+100*30+80*30+90*20)/100 = 9200/100 = 92
  assert.equal(r.total, 92);
  assert.equal(r.incomplete, 0);
  assert.deepEqual(r.missing, []);
});

test('scoreInternComponents：缺企业评价时按已到位权重折算并标记 incomplete', () => {
  const r = benchmarkModel.scoreInternComponents([
    { key: 'checkin', score: 90, weight: 20 },
    { key: 'log', score: 80, weight: 30 },
    { key: 'enterprise', score: null, weight: 30 },
    { key: 'school', score: null, weight: 20 },
  ]);
  // 折算：(90*20+80*30)/(20+30) = (1800+2400)/50 = 84
  assert.equal(r.total, 84);
  assert.equal(r.incomplete, 1);
  assert.deepEqual(r.missing.sort(), ['enterprise', 'school']);
});

test('scoreInternComponents：完全无分项返回 null，不凭空造分', () => {
  const r = benchmarkModel.scoreInternComponents([
    { key: 'checkin', score: null, weight: 20 },
    { key: 'enterprise', score: null, weight: 30 },
  ]);
  assert.equal(r.total, null);
  assert.equal(r.incomplete, 1);
});
