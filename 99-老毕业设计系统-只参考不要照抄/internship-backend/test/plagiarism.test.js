/**
 * 查重对接层单元测试（演示模式）
 * 运行：npm run test:unit
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');

test('未配置第三方时为演示模式，结果带 isDemo 标记', async () => {
  delete process.env.PLAGIARISM_API_URL;
  // 清掉缓存以读取最新环境
  delete require.cache[require.resolve('../utils/plagiarism')];
  const plagiarism = require('../utils/plagiarism');
  assert.equal(plagiarism.isConfigured(), false);
  const r = await plagiarism.detect('/uploads/demo.pdf');
  assert.equal(r.isDemo, true);
  assert.equal(r.provider, 'demo');
  assert.equal(typeof r.similarity, 'number');
  assert.ok(r.similarity >= 0 && r.similarity <= 100);
});

test('配置第三方后判定为已对接（isConfigured=true）', () => {
  process.env.PLAGIARISM_API_URL = 'https://example.com/api/check';
  delete require.cache[require.resolve('../utils/plagiarism')];
  const plagiarism = require('../utils/plagiarism');
  assert.equal(plagiarism.isConfigured(), true);
  delete process.env.PLAGIARISM_API_URL; // 复原
});
