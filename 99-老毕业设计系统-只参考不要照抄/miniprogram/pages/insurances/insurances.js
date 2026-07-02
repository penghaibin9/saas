const { get } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/insurances?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (i) {
        return Object.assign({}, i, { rangeText: fmtDate(i.start_date) + ' ~ ' + fmtDate(i.end_date) });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  }
});
