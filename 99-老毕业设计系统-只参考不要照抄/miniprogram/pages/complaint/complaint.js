const { get, request } = require('../../utils/request');

const CAT = [
  { v: 'complaint', label: '投诉' },
  { v: 'incident', label: '异常情况' },
  { v: 'safety', label: '安全事件' }
];
const ST = { 0: '待处理', 1: '处理中', 2: '已处理', 3: '已关闭' };
const STC = { 0: 'tag-y', 1: 'tag-b', 2: 'tag-g', 3: 'tag-m' };

Page({
  data: {
    loading: true, err: '', list: [], showForm: false,
    category: 'complaint', title: '', content: '', phone: '', urgency: 1, submitting: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/complaints?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (c) {
        return Object.assign({}, c, {
          stText: ST[c.status] || '', stClass: STC[c.status] || 'tag-m',
          catText: (CAT.find(function (x) { return x.v === c.category; }) || {}).label || c.category
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  openForm() { this.setData({ showForm: true }); },
  closeForm() { this.setData({ showForm: false }); },
  noop() {},
  onCat(e) { this.setData({ category: e.currentTarget.dataset.v }); },
  onTitle(e) { this.setData({ title: e.detail.value }); },
  onContent(e) { this.setData({ content: e.detail.value }); },
  onPhone(e) { this.setData({ phone: e.detail.value }); },
  onUrgency(e) { this.setData({ urgency: Number(e.detail.value) + 1 }); },

  submit() {
    const title = (this.data.title || '').trim();
    if (!title) { wx.showToast({ title: '请填写标题', icon: 'none' }); return; }
    this.setData({ submitting: true });
    const that = this;
    request('/complaints', {
      method: 'POST',
      data: {
        category: this.data.category, title: title,
        content: (this.data.content || '').trim(),
        contact_phone: (this.data.phone || '').trim(),
        urgency: this.data.urgency
      }
    }).then(function (res) {
      that.setData({ submitting: false, showForm: false, title: '', content: '', phone: '' });
      wx.showToast({ title: (res.data && res.data.message) || '已提交', icon: 'none' });
      that.load();
    }).catch(function (e) {
      that.setData({ submitting: false });
      wx.showToast({ title: e.message || '提交失败', icon: 'none' });
    });
  }
});
