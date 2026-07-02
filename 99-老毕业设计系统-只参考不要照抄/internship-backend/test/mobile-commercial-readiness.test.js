const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.join(__dirname, '..', '..');
const h5 = fs.readFileSync(path.join(root, 'web', 'm', 'index.html'), 'utf8');
const sw = fs.readFileSync(path.join(root, 'web', 'm', 'sw.js'), 'utf8');
const request = fs.readFileSync(path.join(root, 'miniprogram', 'utils', 'request.js'), 'utf8');
const login = fs.readFileSync(path.join(root, 'miniprogram', 'pages', 'login', 'login.wxml'), 'utf8');

test('移动 H5 不依赖公共 CDN', () => {
  assert.doesNotMatch(h5 + sw, /cdn\.jsdelivr\.net|fonts\.googleapis\.com|unpkg\.com/);
});

test('移动 H5 包含弱网、离线、安全区与动态视口适配', () => {
  assert.match(h5, /networkBar/);
  assert.match(h5, /safe-area-inset-bottom/);
  assert.match(h5, /100dvh/);
  assert.match(sw, /checkinQueue/);
});

test('学生首页保险预警使用已定义时间戳', () => {
  assert.match(h5, /const nowMs=Date\.now\(\)/);
  assert.match(h5, /getTime\(\)>=nowMs/);
  assert.match(h5, /getTime\(\)-nowMs/);
});

test('小程序 API 与学校品牌支持交付配置', () => {
  assert.match(request, /ext\.apiBase/);
  assert.match(login, /\{\{schoolName\}\}/);
  assert.doesNotMatch(login, /湖南石化职院/);
});

test('移动端不出现省平台模块', () => {
  assert.doesNotMatch(h5 + login, /省平台|省厅/);
});
