const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..');
const demoPage = path.join(root, 'web', '演示UI.html');

test('公开销售演示页存在并连接固定演示接口', () => {
  assert.equal(fs.existsSync(demoPage), true);
  const html = fs.readFileSync(demoPage, 'utf8');
  const appSource = fs.readFileSync(path.join(root, 'internship-backend', 'app.js'), 'utf8');
  assert.match(appSource, /['"]\/demo['"]:\s*['"]演示UI\.html['"]/);
  assert.match(html, /\/api\/v1\/public\/product-overview-demo/);
  assert.match(html, /固定脱敏样例/);
  assert.match(html, /不连接、不展示任何学校真实学生信息/);
  assert.doesNotMatch(html, /<script\s+src=/i, '演示页不依赖会被 CSP 拦截的外部脚本');
  assert.doesNotMatch(html, /\.innerHTML\s*=/, '接口数据不得通过 innerHTML 注入页面');
});

test('生产 Nginx 配置显式映射 /demo，不落入管理端 fallback', () => {
  for (const name of ['nginx.conf', 'nginx.conf.example']) {
    const source = fs.readFileSync(path.join(root, 'internship-backend', 'deploy', name), 'utf8');
    const block = source.match(/location = \/demo \{[\s\S]*?\n\s*\}/);
    assert.ok(block, `${name} 必须显式声明 /demo`);
    assert.match(block[0], /演示UI\.html/);
  }
});

test('demoOnly 在任何数据库查询前返回固定聚合数据', async () => {
  const tenancy = require('../config/tenancy');
  const model = require('../models/schoolReadinessModel');
  const originalReadPool = tenancy.getReadPoolForCurrentRequest;
  let queryCount = 0;

  tenancy.getReadPoolForCurrentRequest = () => ({
    query: async () => {
      queryCount += 1;
      throw new Error('demo route must not query database');
    }
  });

  try {
    const result = await model.overview({ preferMockWhenEmpty: true, demoOnly: true });
    assert.equal(queryCount, 0);
    assert.equal(result.source, 'mock-public-demo');
    assert.ok(result.kpis.students > 0);
    assert.ok(result.collegeRanking.length > 0);
  } finally {
    tenancy.getReadPoolForCurrentRequest = originalReadPool;
  }
});
