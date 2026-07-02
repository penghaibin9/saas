/** 登录后请求订阅消息授权（未配置模板 ID 时静默跳过） */
const TMPL_IDS = [
  // 可在微信公众平台配置后填入，例如：'xxxx'
].filter(Boolean);

function requestAfterLogin() {
  if (!TMPL_IDS.length) return;
  wx.requestSubscribeMessage({
    tmplIds: TMPL_IDS,
    fail() {}
  });
}

function bindOpenid() {
  const { request } = require('./request');
  return new Promise(function (resolve) {
    wx.login({
      success(r) {
        if (!r.code) { resolve(); return; }
        request('/wechat/bind-openid', { method: 'POST', data: { code: r.code } })
          .then(function () { resolve(); })
          .catch(function () { resolve(); });
      },
      fail() { resolve(); }
    });
  });
}

module.exports = { requestAfterLogin, bindOpenid };
