const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const DOC = { proposal: '开题', midterm: '中期', draft: '初稿', final: '定稿', other: '其他' };

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-achievements?page_size=30').then(function (d) {
      const ids = ((d && d.list) || []).map(function (a) { return a.id; });
      const tasks = ids.map(function (id) {
        return get('/benchmark/plagiarism/' + id).catch(function () { return null; });
      });
      return Promise.all(tasks).then(function (plags) {
        const list = ((d && d.list) || []).map(function (a, i) {
          const p = plags[i];
          const rate = p && (p.similarity_rate != null ? p.similarity_rate : p.similarity);
          return Object.assign({}, a, {
            dateText: fmtDate(a.create_time),
            docLabel: DOC[a.doc_type] || a.doc_type || '成果',
            rateText: rate != null ? rate + '%' : '未检测',
            rateClass: rate != null && rate > 30 ? 'tag-r' : (rate != null ? 'tag-g' : 'tag-m')
          });
        });
        that.setData({ loading: false, list: list });
        if (done) done();
      });
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  goAchievements() {
    wx.navigateTo({ url: '/pages/achievements/achievements' });
  },

  runCheck(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    wx.showLoading({ title: '检测中' });
    request('/benchmark/plagiarism/' + id, { method: 'POST', data: {} }).then(function (res) {
      wx.hideLoading();
      const d = (res.data && res.data.data) || {};
      const sim = d.similarity_rate != null ? d.similarity_rate : d.similarity;
      const lines = [
        '相似度：' + (sim != null ? sim + '%' : '-'),
        'AIGC 疑似：' + (d.aigc_rate != null ? d.aigc_rate + '%' : '-'),
        '状态：' + (d.status === 1 ? '检测完成' : '需关注')
      ];
      if (d.is_demo) lines.push('（演示数据，未对接查重服务）');
      wx.showModal({ title: '查重结果', content: lines.join('\n'), showCancel: false });
      that.load();
    }).catch(function (err) {
      wx.hideLoading();
      wx.showToast({ title: err.message || '检测失败', icon: 'none' });
    });
  }
});
