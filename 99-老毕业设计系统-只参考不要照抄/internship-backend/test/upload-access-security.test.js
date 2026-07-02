const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const backend = path.resolve(__dirname, '..');
const root = path.resolve(backend, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

test('Express 与 Nginx 均禁止匿名直出 uploads', () => {
  const app = read('internship-backend/app.js');
  const nginx = read('internship-backend/deploy/nginx.conf');
  const nginxExample = read('internship-backend/deploy/nginx.conf.example');

  assert.match(app, /app\.use\(['"]\/uploads['"],\s*tenantMiddleware,\s*authMiddleware,\s*express\.static/);
  for (const source of [nginx, nginxExample]) {
    const block = source.match(/location \/uploads\/ \{[\s\S]*?\n\s*\}/);
    assert.ok(block, '必须显式配置 /uploads/');
    assert.doesNotMatch(block[0], /\balias\b/);
    assert.match(block[0], /proxy_pass/);
  }
});

test('各客户端通过带令牌请求打开本地附件', () => {
  const admin = read('web/管理平台.html');
  const mobile = read('web/m/index.html');
  const miniCheckin = read('miniprogram/pages/checkin/checkin.js');
  const miniRequest = read('miniprogram/utils/request.js');

  assert.match(admin, /async function openProtectedFile/);
  assert.match(admin, /Authorization:\s*'Bearer '/);
  assert.match(admin, /\['http:',\s*'https:'\]\.includes\(target\.protocol\)/);
  assert.doesNotMatch(admin, /href="\$\{[^}]*\.file_url\}"\s+target="_blank"/);
  assert.match(mobile, /async function openProtectedFile/);
  assert.match(mobile, /\['http:',\s*'https:'\]\.includes\(target\.protocol\)/);
  assert.doesNotMatch(mobile, /<img src="\$\{c\.photo_url\}"/);
  assert.match(miniCheckin, /downloadFile\(record\.photoPath\)/);
  assert.match(miniRequest, /startsWith\(['"]\/uploads\/['"]\)/);
  assert.match(miniRequest, /base\.replace\(\/\\\/api/);
  assert.match(miniRequest, /token && !isExternal/);
});
