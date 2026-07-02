const { get, request } = require('../../utils/request');

const ST = { 0: '待审阅', 1: '通过', 2: '驳回', 3: '未完成' };
const STC = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-r', 3: 'tag-m' };

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/quality-checks?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (q) {
        return Object.assign({}, q, {
          statusText: ST[q.status] || '', statusClass: STC[q.status] || 'tag-m',
          typeText: (q.check_type === 'sample' ? '抽查' : '普查') + '/' + (q.scope === 'self' ? '自查' : '互查')
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  pass(e) { this.review(e.currentTarget.dataset.id, 1); },
  reject(e) {
    const id = e.currentTarget.dataset.id, that = this;
    wx.showModal({
      title: '驳回', editable: true, placeholderText: '请填写驳回意见',
      success(r) {
        if (!r.confirm) return;
        if (!(r.content || '').trim()) { wx.showToast({ title: '请填写意见', icon: 'none' }); return; }
        that.review(id, 2, (r.content || '').trim());
      }
    });
  },

  review(id, status, opinion) {
    const that = this;
    const data = { status: status };
    if (opinion) data.opinion = opinion;
    request('/quality-checks/' + id + '/review', { method: 'PUT', data: data }).then(function (res) {
      wx.showToast({ title: res.data && res.data.success ? '已处理' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    });
  }
});
