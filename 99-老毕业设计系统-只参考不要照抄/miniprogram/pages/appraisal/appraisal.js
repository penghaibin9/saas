const { get, uploadFile, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');
const app = getApp();

const ST = { 0: '待教师审核', 1: '已通过', 2: '已退回' };
const STC = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-r' };

Page({
  data: {
    loading: true, err: '', list: [], isTeacher: false,
    fFile: null, fComment: '', uploading: false
  },

  onShow() {
    this.setData({ isTeacher: app.isTeacher() });
    this.load();
  },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/benchmark/appraisals?page_size=20').then(function (d) {
      const list = ((d && d.list) || []).map(function (x) {
        return Object.assign({}, x, {
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

  chooseFile() {
    const that = this;
    wx.chooseMessageFile({
      count: 1, type: 'file', extension: ['pdf', 'jpg', 'jpeg', 'png'],
      success(res) { that.setData({ fFile: res.tempFiles[0] }); }
    });
  },
  onComment(e) { this.setData({ fComment: e.detail.value }); },

  upload() {
    if (!this.data.fFile) { wx.showToast({ title: '请选择鉴定表扫描件', icon: 'none' }); return; }
    const that = this;
    this.setData({ uploading: true });
    uploadFile('/benchmark/appraisals', this.data.fFile.path, {
      enterprise_comment: this.data.fComment || ''
    }, 'file').then(function (res) {
      that.setData({ uploading: false, fFile: null, fComment: '' });
      wx.showToast({ title: res.data && res.data.success ? '已提交' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    }).catch(function (e) { that.setData({ uploading: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  },

  review(e) {
    const id = e.currentTarget.dataset.id;
    const pass = e.currentTarget.dataset.pass === '1';
    const that = this;
    wx.showModal({
      title: pass ? '通过' : '驳回', editable: !pass, placeholderText: '驳回原因',
      success(r) {
        if (!r.confirm) return;
        request('/benchmark/appraisals/' + id + '/review', {
          method: 'PUT', data: { status: pass ? 1 : 2, reject_reason: r.content || '' }
        }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已处理' : (res.data.message || '失败'), icon: 'none' });
          that.load();
        });
      }
    });
  }
});
