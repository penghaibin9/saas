const { get } = require('../../utils/request');

const ST = { 0: '待确认', 1: '已确定', 2: '已驳回' };
const STC = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-r' };

Page({
  data: { loading: true, err: '', list: [], showDetail: false, detail: null },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-topics?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (t) {
        return Object.assign({}, t, { statusText: ST[t.status] || '', statusClass: STC[t.status] || 'tag-m' });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  noop() {},
  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); }
});
