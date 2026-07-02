const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const wechatController = require('../controllers/wechatController');

function responseCapture() {
  return {
    statusCode: 200,
    body: null,
    status(code) { this.statusCode = code; return this; },
    json(body) { this.body = body; return body; }
  };
}

test('微信扫码流程明确标记为演示身份确认', () => {
  const created = responseCapture();
  wechatController.createQr({}, created);
  assert.equal(created.statusCode, 200);
  assert.equal(created.body.data.isDemo, true);
  assert.equal(created.body.data.mode, 'password-confirmation');
  assert.match(created.body.message, /非微信身份认证/);

  const polled = responseCapture();
  wechatController.poll({ params: { ticket: created.body.data.ticket } }, polled);
  assert.equal(polled.body.data.status, 'pending');
  assert.equal(polled.body.data.isDemo, true);
});

test('已下架模块不出现在 PC 页面或产品路由', () => {
  const ui = fs.readFileSync(path.join(__dirname, '..', '..', 'web', '管理平台.html'), 'utf8');
  const routes = fs.readFileSync(path.join(__dirname, '..', 'routes', 'index.js'), 'utf8');
  assert.doesNotMatch(ui, /page:'province'|renderProvince|\/province\//);
  assert.doesNotMatch(routes, /router\.use\('\/province'/);
});
