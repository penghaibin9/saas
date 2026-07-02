const { get, request, uploadFile } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const ST = { 0: '待审阅', 1: '通过', 2: '驳回', 3: '未完成' };
const STC = { 0: 'tag-m', 1: 'tag-g', 2: 'tag-r', 3: 'tag-y' };
const DOC = [
  { value: 'proposal', label: '开题报告' },
  { value: 'midterm', label: '中期检查' },
  { value: 'draft', label: '论文初稿' },
  { value: 'final', label: '论文定稿' },
  { value: 'other', label: '其他成果' }
];

Page({
  data: {
    loading: true,
    err: '',
    list: [],
    docTypes: DOC,
    docIdx: 0,
    showForm: false,
    editId: null,
    fTitle: '',
    fLink: '',
    fFile: null,
    fErr: '',
    saving: false,
    showDetail: false,
    detail: null
  },

  chooseFile() {
    const that = this;
    wx.chooseMessageFile({
      count: 1, type: 'file', extension: ['pdf', 'doc', 'docx', 'zip'],
      success(res) { that.setData({ fFile: res.tempFiles[0] }); }, fail() {}
    });
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-achievements?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (a) {
        const dl = DOC.find(function (x) { return x.value === a.doc_type; });
        return Object.assign({}, a, {
          dateText: fmtDate(a.create_time),
          statusText: ST[a.status] || '',
          statusClass: STC[a.status] || 'tag-m',
          docLabel: dl ? dl.label : '成果'
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
  openForm() { this.setData({ showForm: true, editId: null, fTitle: '', fLink: '', fFile: null, docIdx: 0, fErr: '' }); },
  closeForm() { this.setData({ showForm: false }); },
  onTitle(e) { this.setData({ fTitle: e.detail.value }); },
  onLink(e) { this.setData({ fLink: e.detail.value }); },
  onDocType(e) { this.setData({ docIdx: Number(e.detail.value) }); },

  submitForm() {
    const title = (this.data.fTitle || '').trim();
    const link = (this.data.fLink || '').trim();
    if (!title) { this.setData({ fErr: '请填写标题' }); return; }
    this.setData({ saving: true, fErr: '' });
    const that = this;
    const editId = this.data.editId;
    const url = editId ? '/gd-achievements/' + editId : '/gd-achievements';
    const method = editId ? 'PUT' : 'POST';
    const doc_type = DOC[this.data.docIdx] ? DOC[this.data.docIdx].value : 'other';
    const payload = { title: title, link: link, doc_type: doc_type };
    const done = function (resData) {
      that.setData({ saving: false });
      if (!(resData && resData.success)) { that.setData({ fErr: (resData && resData.message) || '提交失败' }); return; }
      that.setData({ showForm: false });
      wx.showToast({ title: editId ? '已重新提交' : '已提交', icon: 'success' });
      that.load();
    };
    if (this.data.fFile && !editId) {
      // 附件仅支持新建上传（wx.uploadFile 仅 POST）
      uploadFile('/gd-achievements', this.data.fFile.path, { title: title, link: link, doc_type: doc_type }, 'file')
        .then(function (res) { done(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    } else {
      request(url, { method: method, data: payload })
        .then(function (res) { done(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    }
  },

  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  resubmit() {
    const a = this.data.detail;
    this.setData({ showDetail: false, showForm: true, editId: a.id, fTitle: a.title, fLink: a.link || '', fErr: '' });
  },

  removeAch() {
    const id = this.data.detail.id, that = this;
    wx.showModal({
      title: '删除成果', content: '确定删除该成果？',
      success(r) {
        if (!r.confirm) return;
        request('/gd-achievements/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已删除' : (res.data.message || '失败'), icon: 'none' });
          that.closeDetail(); that.load();
        });
      }
    });
  }
});
