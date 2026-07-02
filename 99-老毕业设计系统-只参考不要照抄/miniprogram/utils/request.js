const config = require('../config');

const ext = typeof wx.getExtConfigSync === 'function' ? (wx.getExtConfigSync() || {}) : {};
const REQUEST_TIMEOUT = 15000;

function getEnvVersion() {
  try {
    const info = wx.getAccountInfoSync();
    return (info && info.miniProgram && info.miniProgram.envVersion) || 'develop';
  } catch (e) {
    return 'develop';
  }
}

function getApiBase() {
  const envVersion = getEnvVersion();
  // extConfig 供第三方平台代开发使用；普通小程序读取 config.js。
  // api_base 仅允许开发版临时覆盖，避免正式版被本地缓存劫持请求地址。
  const devOverride = envVersion === 'develop' ? wx.getStorageSync('api_base') : '';
  return String(ext.apiBase || devOverride || config.apiBase[envVersion] || config.apiBase.develop || '').replace(/\/$/, '');
}

function assertApiBase(base) {
  const envVersion = getEnvVersion();
  if (!base) throw new Error('尚未配置服务器地址，请修改 miniprogram/config.js');
  if (envVersion !== 'develop' && !/^https:\/\//i.test(base)) {
    throw new Error('体验版和正式版必须使用 HTTPS 服务器地址');
  }
  if (envVersion !== 'develop' && /example\.com/i.test(base)) {
    throw new Error('请先把 config.js 中的示例域名换成你的真实域名');
  }
  return base;
}

function apiUrl(path) {
  return assertApiBase(getApiBase()) + path;
}

function buildHeaders(customHeader) {
  const token = wx.getStorageSync('token');
  const header = Object.assign({ 'Content-Type': 'application/json' }, customHeader || {});
  if (token) header['Authorization'] = 'Bearer ' + token;
  return header;
}

function request(path, options) {
  options = options || {};
  const method = options.method || 'GET';
  const data = options.data;
  const header = buildHeaders(options.header);
  const timeout = options.timeout || REQUEST_TIMEOUT;
  const showLoading = options.showLoading || false;

  const app = getApp();
  if (app && app.globalData && app.globalData.online === false) {
    return Promise.reject(new Error('网络未连接，请检查网络'));
  }

  if (showLoading) wx.showLoading({ title: options.loadingTitle || '加载中', mask: true });

  return new Promise(function (resolve, reject) {
    let url;
    try { url = apiUrl(path); } catch (e) { return reject(e); }
    wx.request({
      url: url,
      method: method,
      data: data,
      header: header,
      timeout: timeout,
      success: function (res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync('token');
          wx.removeStorageSync('user');
          wx.showToast({ title: '登录已过期', icon: 'none' });
          wx.reLaunch({ url: '/pages/login/login' });
          return reject(new Error('登录已过期'));
        }
        if (res.statusCode === 403 && res.data && res.data.data && res.data.data.code === 'MUST_CHANGE_PASSWORD') {
          wx.navigateTo({ url: '/pages/profile/profile?force=1' });
          return reject(new Error('请先修改初始密码'));
        }
        if (res.statusCode >= 500) {
          return reject(new Error('服务暂时不可用，请稍后重试'));
        }
        resolve(res);
      },
      fail: function (err) {
        const detail = err && err.errMsg ? '（' + err.errMsg + '）' : '';
        reject(new Error('网络连接失败，请检查服务器地址和合法域名' + detail));
      },
      complete: function () {
        if (showLoading) wx.hideLoading();
      }
    });
  });
}

// 直接拿业务 data 字段；失败抛出可读错误（供页面统一展示重试）
function get(path, options) {
  return request(path, Object.assign({ method: 'GET' }, options)).then(function (res) {
    if (res.data && res.data.success) return res.data.data;
    throw new Error((res.data && res.data.message) || '加载失败');
  });
}

// 上传文件（multipart）。filePath 为本地临时路径，name 默认字段名 file，formData 为附带的文本字段
function uploadFile(path, filePath, formData, name, options) {
  options = options || {};
  const app = getApp();
  if (app && app.globalData && app.globalData.online === false) {
    return Promise.reject(new Error('网络未连接，请检查网络'));
  }
  const token = wx.getStorageSync('token');
  const header = buildHeaders();
  return new Promise(function (resolve, reject) {
    let url;
    try { url = apiUrl(path); } catch (e) { return reject(e); }
    wx.uploadFile({
      url: url,
      filePath: filePath,
      name: name || 'file',
      formData: formData || {},
      header: header,
      timeout: options.timeout || REQUEST_TIMEOUT,
      success: function (res) {
        let data = null;
        try { data = JSON.parse(res.data); } catch (e) { data = null; }
        if (res.statusCode === 401) {
          wx.removeStorageSync('token'); wx.removeStorageSync('user');
          wx.reLaunch({ url: '/pages/login/login' });
          return reject(new Error('登录已过期'));
        }
        resolve({ statusCode: res.statusCode, data: data });
      },
      fail: function () { reject(new Error('上传失败，请检查网络')); }
    });
  });
}

function downloadFile(path, options) {
  options = options || {};
  const app = getApp();
  if (app && app.globalData && app.globalData.online === false) {
    return Promise.reject(new Error('网络未连接，请检查网络'));
  }
  const token = wx.getStorageSync('token');
  const isExternal = /^https?:\/\//i.test(String(path || ''));
  // 绝不把本系统 JWT 发送到外部对象存储域名；外部地址应由服务端生成短期签名 URL。
  const header = token && !isExternal ? { Authorization: 'Bearer ' + token } : {};
  // 业务下载接口位于 /api；受保护的原始上传件位于站点根 /uploads。
  return new Promise(function (resolve, reject) {
    let base = '';
    try { base = isExternal ? '' : assertApiBase(getApiBase()); } catch (e) { return reject(e); }
    const url = isExternal
      ? String(path)
      : String(path || '').startsWith('/uploads/')
        ? base.replace(/\/api\/?$/, '') + path
        : base + path;
    wx.downloadFile({
      url: url,
      header: header,
      timeout: options.timeout || REQUEST_TIMEOUT,
      success: function (res) {
        if (res.statusCode === 401) {
          wx.removeStorageSync('token'); wx.removeStorageSync('user');
          wx.showToast({ title: '登录已过期', icon: 'none' });
          wx.reLaunch({ url: '/pages/login/login' });
          return reject(new Error('登录已过期'));
        }
        if (res.statusCode !== 200) {
          return reject(new Error('下载失败'));
        }
        resolve(res);
      },
      fail: function () { reject(new Error('下载失败，请检查网络')); }
    });
  });
}

module.exports = {
  request: request,
  get: get,
  uploadFile: uploadFile,
  downloadFile: downloadFile,
  getApiBase: getApiBase,
  getEnvVersion: getEnvVersion
};
