const { get, request } = require('../../utils/request');

const LV = { high: '高危', medium: '提醒', low: '关注' };
const LVC = { high: 'tag-r', medium: 'tag-y', low: 'tag-m' };

Page({
  data: { loading: true, err: '', summary: { high: 0, medium: 0, low: 0, students: 0 }, list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/risk/warnings').then(function (d) {
      const summary = (d && d.summary) || { high: 0, medium: 0, low: 0, students: 0 };
      const list = ((d && d.list) || []).map(function (w) {
        return Object.assign({}, w, { levelText: LV[w.level] || '', levelClass: LVC[w.level] || 'tag-m' });
      });
      that.setData({ loading: false, summary: summary, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  notifyAll() {
    const that = this;
    wx.showModal({
      title: '一键提醒', content: '将向所有被预警学生发送站内提醒，确认？',
      success(r) {
        if (!r.confirm) return;
        request('/risk/notify', { method: 'POST', data: {} }).then(function (res) {
          wx.showToast({ title: (res.data && res.data.message) || '已发送', icon: 'none' });
        });
      }
    });
  }
});
