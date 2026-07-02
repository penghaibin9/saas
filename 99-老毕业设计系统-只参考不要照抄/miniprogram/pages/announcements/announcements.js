const { get } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

Page({
  data: { loading: true, err: '', list: [], showDetail: false, detail: null },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/announcements?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (a) {
        return Object.assign({}, a, {
          dateText: fmtDate(a.publish_time || a.create_time),
          by: a.publisher_name || a.college_name || ''
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  noop() {},
  openDetail(e) {
    const base = e.currentTarget.dataset.item;
    const that = this;
    this.setData({ showDetail: true, detail: base });
    get('/announcements/' + base.id).then(function (full) {
      if (full) that.setData({ detail: Object.assign({}, base, full, { dateText: base.dateText, by: base.by }) });
    }).catch(function () {});
  },
  closeDetail() { this.setData({ showDetail: false, detail: null }); }
});
