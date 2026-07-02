const { get, request } = require('../../utils/request');
const { fmtDate, toDate } = require('../../utils/util');

const ST = { 0: '草稿', 1: '待教师审核', 2: '已通过', 3: '已退回' };
const STC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g', 3: 'tag-r' };

Page({
  data: {
    loading: true,
    err: '',
    list: [],
    showForm: false,
    fStart: '',
    fEnd: '',
    fReason: '',
    fDays: 0,
    fErr: '',
    saving: false,
    showDetail: false,
    detail: null
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/leaves?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (l) {
        return Object.assign({}, l, {
          startText: fmtDate(l.start_date),
          endText: fmtDate(l.end_date),
          statusText: ST[l.status] || '',
          statusClass: STC[l.status] || 'tag-m'
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
  openForm() { this.setData({ showForm: true, fStart: '', fEnd: '', fReason: '', fErr: '' }); },
  closeForm() { this.setData({ showForm: false }); },
  onStart(e) { this.setData({ fStart: e.detail.value }); this.calcDays(); },
  onEnd(e) { this.setData({ fEnd: e.detail.value }); this.calcDays(); },

  calcDays() {
    const s = toDate(this.data.fStart), e = toDate(this.data.fEnd);
    let days = 0;
    if (s && e && e >= s) days = Math.round((e - s) / 86400000) + 1;
    this.setData({ fDays: days });
  },
  onReason(e) { this.setData({ fReason: e.detail.value }); },

  submitForm() {
    const s = this.data.fStart, en = this.data.fEnd, reason = (this.data.fReason || '').trim();
    if (!s || !en || !reason) { this.setData({ fErr: '请填写完整' }); return; }
    if (en < s) { this.setData({ fErr: '结束日期不能早于开始日期' }); return; }
    if (reason.length < 5) { this.setData({ fErr: '请假事由请不少于 5 个字' }); return; }
    this.setData({ saving: true, fErr: '' });
    const that = this;
    request('/leaves', { method: 'POST', data: { start_date: s, end_date: en, reason: reason } })
      .then(function (res) {
        if (!(res.data && res.data.success)) { that.setData({ saving: false, fErr: res.data.message || '提交失败' }); return; }
        return request('/leaves/' + res.data.data.id + '/submit', { method: 'PUT' }).then(function () {
          that.setData({ saving: false, showForm: false });
          wx.showToast({ title: '已提交', icon: 'success' });
          that.load();
        });
      })
      .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
  },

  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  submitDraft() {
    const id = this.data.detail.id, that = this;
    request('/leaves/' + id + '/submit', { method: 'PUT' }).then(function (res) {
      wx.showToast({ title: res.data && res.data.success ? '已提交' : (res.data.message || '失败'), icon: 'none' });
      that.closeDetail(); that.load();
    });
  },

  removeDraft() {
    const id = this.data.detail.id, that = this;
    wx.showModal({
      title: '删除草稿', content: '确定删除该草稿？',
      success(r) {
        if (!r.confirm) return;
        request('/leaves/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已删除' : (res.data.message || '失败'), icon: 'none' });
          that.closeDetail(); that.load();
        });
      }
    });
  }
});
