const app = getApp();
const { request, getEnvVersion } = require('../../utils/request');
const { bindOpenid, requestAfterLogin } = require('../../utils/subscribe');
const config = require('../../config');

Page({
  data: { username: '', password: '', err: '', loading: false, mode: 'login', schoolName: '示范院校', graduationYear: '', legalAccepted: false, enableDemoAccounts: false },

  onLoad() {
    this.setData({
      schoolName: app.globalData.schoolName,
      graduationYear: app.globalData.graduationYear,
      legalAccepted: wx.getStorageSync('legal_version') === config.legalVersion,
      enableDemoAccounts: !!config.demoAccounts[getEnvVersion()]
    });
  },

  onShow() {
    const token = wx.getStorageSync('token');
    const user = wx.getStorageSync('user');
    if (token && user) {
      if (user.role === 5) wx.reLaunch({ url: '/pages/enterprise/index/index' });
      else wx.switchTab({ url: '/pages/home/home' });
    }
  },

  onUser(e) { this.setData({ username: e.detail.value }); },
  onPwd(e) { this.setData({ password: e.detail.value }); },
  onLegalChange(e) { this.setData({ legalAccepted: (e.detail.value || []).includes('accepted') }); },
  openLegal(e) { wx.navigateTo({ url: '/pages/legal/legal?tab=' + (e.currentTarget.dataset.tab || 'privacy') }); },

  fillDemo(e) {
    const u = e.currentTarget.dataset.u || 'demo_stu1';
    this.setData({ username: u, password: 'demo1234', err: '' });
  },

  doLogin() {
    const username = (this.data.username || '').trim();
    const password = this.data.password || '';
    if (!username || !password) { this.setData({ err: '请输入账号密码' }); return; }
    if (!this.data.legalAccepted) { this.setData({ err: '请先阅读并同意隐私政策与用户协议' }); return; }
    wx.setStorageSync('legal_version', config.legalVersion);
    this.setData({ err: '', loading: true });
    const that = this;
    request('/users/login', { method: 'POST', data: { username, password } })
      .then(function (res) {
        const body = res.data;
        if (!(body && body.success)) {
          that.setData({ err: (body && body.message) || '登录失败', loading: false });
          return;
        }
        const d = body.data;
        if (d.user.role < 3 && d.user.role !== 5) {
          that.setData({ err: '请使用学生/教师/企业账号登录', loading: false });
          return;
        }
        app.setToken(d.token);
        app.setUser(d.user);
        that.setData({ loading: false });
        bindOpenid().then(function () {
          requestAfterLogin();
          if (d.mustChangePassword) {
            wx.navigateTo({ url: '/pages/profile/profile?force=1' });
            return;
          }
          if (d.user.role === 5) wx.reLaunch({ url: '/pages/enterprise/index/index' });
          else wx.switchTab({ url: '/pages/home/home' });
        });
      })
      .catch(function (e) { that.setData({ err: e.message || '登录失败', loading: false }); });
  },

  toEnterpriseH5() {
    wx.showModal({
      title: '企业入驻',
      content: '完整入驻注册请在浏览器打开 H5 企业端，或使用企业账号直接登录小程序。',
      showCancel: false
    });
  }
});
