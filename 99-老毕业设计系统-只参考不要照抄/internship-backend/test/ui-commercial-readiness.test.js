const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..');
const admin = fs.readFileSync(path.join(root, 'web', '管理平台.html'), 'utf8');
const demo = fs.readFileSync(path.join(root, 'web', '演示UI.html'), 'utf8');
const routes = fs.readFileSync(path.join(__dirname, '..', 'routes', 'index.js'), 'utf8');

test('正式 PC 导航不展示省平台模块', () => {
  assert.doesNotMatch(admin, /\{page:'province'/);
  assert.doesNotMatch(admin, /province:renderProvince/);
});

test('省平台 API 未挂载到产品路由', () => {
  assert.doesNotMatch(routes, /router\.use\('\/province'/);
});

test('正式 PC 入口不依赖公共字体或脚本 CDN', () => {
  assert.doesNotMatch(admin, /fonts\.googleapis\.com|cdn\.jsdelivr\.net|unpkg\.com/);
});

test('公开演示页不宣传省平台能力', () => {
  assert.doesNotMatch(demo, /省平台|省厅/);
});
