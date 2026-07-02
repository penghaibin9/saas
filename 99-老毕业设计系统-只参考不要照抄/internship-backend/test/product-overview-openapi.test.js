const test = require('node:test');
const assert = require('node:assert/strict');
const buildSpec = require('../openapi/spec');

test('OpenAPI 明确公开演示与真实管理员概览的权限边界', () => {
  const spec = buildSpec('https://school.example');
  const publicDemo = spec.paths['/public/product-overview-demo'].get;
  const realStats = spec.paths['/stats/product-overview'].get;

  assert.deepEqual(publicDemo.security, []);
  assert.match(publicDemo.summary, /不读取学校真实数据库/);
  assert.ok(publicDemo.responses[200]);
  assert.ok(realStats.responses[401]);
  assert.ok(realStats.responses[403]);
  assert.match(realStats.summary, /仅院校\/二级学院管理员/);
  assert.ok(spec.components.schemas.ProductOverview);
});
