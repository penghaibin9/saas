const { get, request } = require('../../utils/request');
const { fmtDate, toDate } = require('../../utils/util');

const ST = { 0: '草稿', 1: '待教师审核', 2: '已通过', 3: '已退回' };
const STC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g', 3: 'tag-r' };

Page({
  data: {
    loading: true,
    err: '',
    list: [],
    shown: [],
    filter: 'all',
    filters: [
      { k: 'all', label: '全部' },
      { k: '0', label: '草稿' },
      { k: '1', label: '待批阅' },
      { k: '2', label: '已通过' },
      { k: '3', label: '已退回' }
    ],
    stats: { total: 0, pending: 0, passed: 0, rejected: 0 },
    weeklyDone: true,
    detail: null,
    showDetail: false
  },

  setFilter(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({ filter: k });
    this.applyFilter();
  },

  applyFilter() {
    const f = this.data.filter;
    const list = this.data.list;
    this.setData({ shown: f === 'all' ? list : list.filter(function (l) { return String(l.status) === f; }) });
  },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(2); }
    this.load();
  },

  onPullDownRefresh() {
    this.load(function () { wx.stopPullDownRefresh(); });
  },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/intern-logs?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (l) {
        return Object.assign({}, l, {
          typeLabel: l.type === 'monthly' ? '[月报] ' : '[周报] ',
          dateText: fmtDate(l.create_time),
          statusText: ST[l.status] || '',
          statusClass: STC[l.status] || 'tag-m'
        });
      });
      // 统计
      const stats = {
        total: list.length,
        pending: list.filter(function (l) { return l.status === 1; }).length,
        passed: list.filter(function (l) { return l.status === 2; }).length,
        rejected: list.filter(function (l) { return l.status === 3; }).length
      };
      // 本周是否已提交周报（状态非草稿，创建时间在本周内）
      const now = new Date();
      const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7));
      const weeklyDone = list.some(function (l) {
        if (l.type === 'monthly' || l.status === 0) return false;
        const d = toDate(l.create_time);
        return d && d >= monday;
      });
      that.setData({ loading: false, list: list, stats: stats, weeklyDone: weeklyDone });
      that.applyFilter();
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  newLog() { wx.navigateTo({ url: '/pages/newlog/newlog' }); },

  openDetail(e) {
    const l = e.currentTarget.dataset.item;
    this.setData({ detail: l, showDetail: true });
  },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },
  noop() {},

  submit() {
    const id = this.data.detail.id;
    const that = this;
    request('/intern-logs/' + id + '/submit', { method: 'PUT' }).then(function (res) {
      wx.showToast({ title: res.data && res.data.success ? '已提交' : (res.data.message || '失败'), icon: 'none' });
      that.closeDetail(); that.load();
    });
  },

  edit() {
    const l = this.data.detail;
    this.closeDetail();
    wx.navigateTo({ url: '/pages/newlog/newlog?id=' + l.id });
  },

  remove() {
    const id = this.data.detail.id;
    const that = this;
    wx.showModal({
      title: '删除草稿', content: '确定删除该草稿？',
      success(r) {
        if (!r.confirm) return;
        request('/intern-logs/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已删除' : (res.data.message || '失败'), icon: 'none' });
          that.closeDetail(); that.load();
        });
      }
    });
  }
});
