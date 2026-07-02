const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

test('product overview implementation files exist', () => {
  assert.ok(fs.existsSync(path.join(root, 'models', 'schoolReadinessModel.js')));
  assert.ok(fs.existsSync(path.join(root, 'routes', 'statsRoutes.js')));
  assert.ok(fs.existsSync(path.join(root, 'routes', 'publicRoutes.js')));
});

test('authenticated product overview route is available under stats', () => {
  const statsRoutes = read('routes/statsRoutes.js');
  assert.ok(statsRoutes.includes('/product-overview'));
  assert.ok(statsRoutes.includes('schoolReadinessModel'));
  assert.match(
    statsRoutes,
    /router\.get\(['"]\/product-overview['"],\s*authMiddleware/,
    '真实产品概览必须经过 authMiddleware'
  );
  assert.match(statsRoutes, /authMiddleware,\s*requireRole\(1,\s*2\)/, '校级聚合数据仅管理员可见');
  assert.ok(statsRoutes.includes("String(req.query.demo || '') === '1'"));
});

test('public demo product overview route is available without exposing raw user records', () => {
  const publicRoutes = read('routes/publicRoutes.js');
  assert.ok(publicRoutes.includes('/product-overview-demo'));
  assert.ok(publicRoutes.includes('preferMockWhenEmpty: true'));
  assert.ok(publicRoutes.includes('demoOnly: true'));
  assert.match(publicRoutes, /const data = \{[\s\S]*source: overview\.source[\s\S]*demoFlow: overview\.demoFlow[\s\S]*\}/);
  assert.equal(publicRoutes.includes('diagnostics: overview.diagnostics'), false);
});

test('public demo overview is aggregate-only and never exposes personal fields', async () => {
  const schoolReadinessModel = require('../models/schoolReadinessModel');
  const result = await schoolReadinessModel.overview({ preferMockWhenEmpty: true, demoOnly: true });

  assert.equal(result.source, 'mock-public-demo');
  assert.ok(result.kpis && typeof result.kpis === 'object');
  assert.ok(Array.isArray(result.collegeRanking));
  assert.match(result.metricDefinitions.inPostStudents, /状态为 3 或 5/);
  assert.match(result.metricDefinitions.riskAlerts, /历史全部打卡/);
  assert.equal(result.metricContext.batchYear, null);

  const serialized = JSON.stringify(result).toLowerCase();
  for (const personalField of ['phone', 'mobile', 'id_card', 'idcard', 'address', 'studentname', 'real_name']) {
    assert.equal(serialized.includes(personalField), false, `演示响应不应包含个人字段 ${personalField}`);
  }
});

test('model sanitizes query errors and does not mix mock rankings into real results', () => {
  const model = read('models/schoolReadinessModel.js');
  assert.ok(model.includes("code: 'STAT_QUERY_FAILED'"));
  assert.equal(model.includes('errors.push({ label, message: err.message })'), false);
  assert.ok(model.includes('const collegeRanking = rankingRows.map'));
});
