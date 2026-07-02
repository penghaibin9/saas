const { get } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const ST = { 0: '筹备中', 1: '进行中', 2: '已完成' };

Page({
  data: { loading: true, err: '', info: null },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/benchmark/defense/mine').then(function (d) {
      const info = d ? Object.assign({}, d, {
        stText: ST[d.status] || '',
        timeText: fmtDate(d.defense_date || d.defense_time || d.start_time),
        scoreText: d.final_score != null ? d.final_score + ' 分' : '待评定'
      }) : null;
      that.setData({ loading: false, info: info });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  }
});
