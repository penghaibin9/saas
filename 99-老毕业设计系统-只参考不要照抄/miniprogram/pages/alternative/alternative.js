const { get, uploadFile, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const TYPES = [
  { value: 'exempt', label: '免实习' },
  { value: 'study', label: '升学' },
  { value: 'business', label: '创业' },
  { value: 'military', label: '参军' },
  { value: 'other', label: '其他' }
];
const ST = { 0: '待审核', 1: '已通过', 2: '已驳回' };
const STC = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-r' };

Page({
  data: {
    loading: true, err: '', list: [], types: TYPES, typeIdx: 0,
    reason: '', fFile: null, submitting: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/benchmark/alternatives?page_size=20').then(function (d) {
      const list = ((d && d.list) || []).map(function (x) {
        const tl = TYPES.find(function (t) { return t.value === x.alt_type; });
        return Object.assign({}, x, {
          typeLabel: tl ? tl.label : x.alt_type,
          dateText: fmtDate(x.create_time),
          statusText: ST[x.status] || '', statusClass: STC[x.status] || 'tag-m'
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  onType(e) { this.setData({ typeIdx: Number(e.detail.value) }); },
  onReason(e) { this.setData({ reason: e.detail.value }); },
  chooseFile() {
    const that = this;
    wx.chooseMessageFile({ count: 1, type: 'file', success(res) { that.setData({ fFile: res.tempFiles[0] }); } });
  },

  submit() {
    const reason = (this.data.reason || '').trim();
    if (!reason) { wx.showToast({ title: '请填写申请原因', icon: 'none' }); return; }
    const t = TYPES[this.data.typeIdx];
    const that = this;
    this.setData({ submitting: true });
    const form = { alt_type: t.value, reason: reason };
    const done = function (res) {
      that.setData({ submitting: false, reason: '', fFile: null });
      wx.showToast({ title: res.data && res.data.success ? '已提交' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    };
    if (this.data.fFile) {
      uploadFile('/benchmark/alternatives', this.data.fFile.path, form, 'file').then(done)
        .catch(function (e) { that.setData({ submitting: false }); wx.showToast({ title: e.message, icon: 'none' }); });
    } else {
      request('/benchmark/alternatives', { method: 'POST', data: form }).then(done)
        .catch(function (e) { that.setData({ submitting: false }); wx.showToast({ title: e.message, icon: 'none' }); });
    }
  }
});
