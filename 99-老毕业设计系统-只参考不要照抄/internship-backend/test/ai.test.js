/**
 * AI 服务层单元测试（不依赖数据库、不依赖外网）
 * 未配置 DEEPSEEK_API_KEY 时走确定性演示降级，结果须带 isDemo=true 且不伪装。
 * 运行：npm run test:unit
 */
delete process.env.DEEPSEEK_API_KEY; // 确保演示模式
process.env.NODE_ENV = 'test';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const ai = require('../utils/ai');

test('未配置时 isConfigured=false，status 为 demo', () => {
  assert.equal(ai.isConfigured(), false);
  assert.equal(ai.status().mode, 'demo');
});

test('scoreLog：演示模式返回 isDemo 且分数在区间内', async () => {
  const r = await ai.scoreLog({ title: '第3周', content: '本周完成了数据库设计与接口联调，遇到分页性能问题，通过加索引解决。\n收获：理解了索引原理。\n下周计划：完成前端对接。', type: 'weekly' });
  assert.equal(r.isDemo, true);
  assert.ok(r.score >= 0 && r.score <= 100);
  assert.ok(Array.isArray(r.suggestions));
});

test('scoreLog：敷衍内容分数明显更低', async () => {
  const lazy = await ai.scoreLog({ content: '今天正常', type: 'weekly' });
  const good = await ai.scoreLog({ content: '本周系统学习了岗位标准作业流程，完成三项任务并记录数据，反思了沟通不足之处，制定了改进计划，内容详实充分扩展说明。', type: 'weekly' });
  assert.ok(good.score > lazy.score);
});

test('analyzeRiskText：命中风险词升级风险等级', async () => {
  const none = await ai.analyzeRiskText({ text: '今天工作顺利' });
  assert.equal(none.level, 'none');
  const high = await ai.analyzeRiskText({ text: '我想辞职，工厂还克扣工资，压力大' });
  assert.equal(high.isDemo, true);
  assert.ok(['medium', 'high'].includes(high.level));
  assert.ok(high.signals.length >= 1);
});

test('matchPositions：按技能命中排序', async () => {
  const r = await ai.matchPositions({
    skills: 'Java,MySQL',
    positions: [
      { id: 1, title: '前端开发', requirement: 'Vue React' },
      { id: 2, title: 'Java后端', requirement: 'Java MySQL Spring' },
    ],
  });
  assert.equal(r.isDemo, true);
  assert.equal(r.ranked[0].positionId, 2); // Java/MySQL 命中更多排第一
});

test('assistantAnswer：演示模式如实标注，不编造制度', async () => {
  const r = await ai.assistantAnswer({ question: '实习报酬最低标准是多少？' });
  assert.equal(r.isDemo, true);
  assert.ok(r.answer.includes('演示'));
});
