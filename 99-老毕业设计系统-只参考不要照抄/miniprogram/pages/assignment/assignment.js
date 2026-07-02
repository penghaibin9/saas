const { get, request } = require('../../utils/request');

Page({
  data: { loading: true, err: '', a: null },

  onShow() { this.load(); },

  load() {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/assignments?page_size=1').then(function (d) {
      that.setData({ loading: false, a: ((d && d.list) || [])[0] || null });
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
    });
  },

  toCheckin() { wx.switchTab({ url: '/pages/checkin/checkin' }); },

  toTransfer() {
    const a = this.data.a;
    if (!a) return;
    wx.navigateTo({ url: '/pages/assignment-change/assignment-change?type=transfer&assignment_id=' + a.id });
  },

  toTerminate() {
    const a = this.data.a;
    if (!a) return;
    wx.navigateTo({ url: '/pages/assignment-change/assignment-change?type=terminate&assignment_id=' + a.id });
  },

  completeIntern() {
    const that = this;
    wx.showModal({
      title: '结束实习',
      content: '实习期满后将提交结束申请并归档，是否继续？',
      success(r) {
        if (!r.confirm) return;
        request('/benchmark/intern-complete', { method: 'POST', data: { reason: '实习期满' } }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '实习已结束' : (res.data.message || '失败'), icon: 'none' });
          that.load();
        }).catch(function (e) { wx.showToast({ title: e.message, icon: 'none' }); });
      }
    });
  }
});
