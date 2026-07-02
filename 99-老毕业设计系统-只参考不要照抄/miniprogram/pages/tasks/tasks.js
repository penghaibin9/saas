const { get } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const ST = { 0: '未开始', 1: '进行中', 2: '已完成' };
const STC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g' };

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-tasks?only_root=1&page_size=100').then(function (d) {
      const list = ((d && d.list) || []).map(function (t) {
        return Object.assign({}, t, {
          statusText: ST[t.status] || '', statusClass: STC[t.status] || 'tag-m',
          reqText: t.require_time ? ('要求:' + fmtDate(t.require_time)) : '',
          actText: t.actual_time ? (' · 完成:' + fmtDate(t.actual_time)) : ''
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  }
});
