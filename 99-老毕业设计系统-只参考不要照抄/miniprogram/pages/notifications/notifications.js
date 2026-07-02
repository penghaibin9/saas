const { get, request } = require('../../utils/request');
const { fmtTime } = require('../../utils/util');

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/notifications?page_size=40').then(function (d) {
      const list = ((d && d.list) || []).map(function (n) {
        return Object.assign({}, n, { timeText: fmtTime(n.create_time) });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  readOne(e) {
    const id = e.currentTarget.dataset.id;
    const isRead = e.currentTarget.dataset.read;
    if (isRead) return;
    const that = this;
    request('/notifications/' + id + '/read', { method: 'PUT' }).then(function () {
      const list = that.data.list.map(function (n) {
        return n.id === id ? Object.assign({}, n, { is_read: 1 }) : n;
      });
      that.setData({ list: list });
    });
  },

  readAll() {
    const that = this;
    request('/notifications/read-all', { method: 'PUT' }).then(function () {
      wx.showToast({ title: '全部已读', icon: 'success' });
      that.load();
    });
  }
});
