const app = getApp();

Page({
  data: { user: {}, isTeacher: false },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(app.isTeacher() ? 2 : 3); }
    this.setData({ user: app.globalData.user || {}, isTeacher: app.isTeacher() });
  },

  nav(e) { wx.navigateTo({ url: e.currentTarget.dataset.url }); },

  logout() {
    wx.showModal({
      title: '退出登录', content: '确定退出当前账号？',
      success(r) { if (r.confirm) app.logout(); }
    });
  }
});
