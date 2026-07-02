const config = require('./config');

App({
  globalData: {
    user: null,
    online: true,
    schoolName: config.schoolName,
    graduationYear: config.graduationYear,
    // 演示模式：仅用于答辩/演示时开启"模拟定位打卡"等便捷功能。
    // 正式售卖/生产环境务必保持 false，避免学生绕过在岗定位校验（防代打卡）。
    demoMode: false
  },

  onLaunch() {
    const ext = typeof wx.getExtConfigSync === 'function' ? (wx.getExtConfigSync() || {}) : {};
    this.globalData.schoolName = ext.schoolName || config.schoolName;
    this.globalData.graduationYear = ext.graduationYear || config.graduationYear;
    this.globalData.user = wx.getStorageSync('user') || null;
    this.initNetworkMonitor();
  },

  onShow() {
    this.globalData.user = wx.getStorageSync('user') || null;
  },

  initNetworkMonitor() {
    const app = this;
    wx.getNetworkType({
      success(res) {
        app.globalData.online = res.networkType !== 'none';
      }
    });
    wx.onNetworkStatusChange(function (res) {
      app.globalData.online = res.isConnected;
    });
  },

  setUser(user) {
    this.globalData.user = user;
    wx.setStorageSync('user', user);
  },

  setToken(token) {
    wx.setStorageSync('token', token);
  },

  getToken() {
    return wx.getStorageSync('token') || null;
  },

  isTeacher() {
    const u = this.globalData.user;
    return !!(u && u.role === 3);
  },

  logout() {
    this.globalData.user = null;
    wx.removeStorageSync('token');
    wx.removeStorageSync('user');
    wx.reLaunch({ url: '/pages/login/login' });
  }
});
