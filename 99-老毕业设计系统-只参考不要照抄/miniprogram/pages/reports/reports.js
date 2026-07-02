const { get, request, uploadFile, downloadFile } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const ST = { 0: '草稿', 1: '已提交', 2: '已评阅' };
const STC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g' };

Page({
  data: {
    loading: true, err: '', list: [],
    showDetail: false, detail: null,
    showForm: false,
    apps: [], appIndex: 0, fTitle: '', fContent: '', fFile: null, fErr: '', saving: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/reports?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (r) {
        return Object.assign({}, r, {
          dateText: fmtDate(r.create_time),
          statusText: ST[r.status] || '', statusClass: STC[r.status] || 'tag-m',
          downloadPath: r.file_url ? '/reports/' + r.id + '/download' : ''
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  noop() {},
  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  openForm() {
    const that = this;
    get('/applications?page_size=50').then(function (d) {
      const ok = ((d && d.list) || []).filter(function (a) { return a.status === 3 || a.status === 5; })
        .map(function (a) { return { id: a.id, label: (a.position_title || '岗位') + '（' + (a.enterprise_name || '') + '）' }; });
      if (!ok.length) { wx.showToast({ title: '需有通过审核的申请', icon: 'none' }); return; }
      that.setData({ showForm: true, apps: ok, appIndex: 0, fTitle: '', fContent: '', fFile: null, fErr: '' });
    });
  },
  closeForm() { this.setData({ showForm: false }); },
  onApp(e) { this.setData({ appIndex: Number(e.detail.value) }); },
  onTitle(e) { this.setData({ fTitle: e.detail.value }); },
  onContent(e) { this.setData({ fContent: e.detail.value }); },

  chooseFile() {
    const that = this;
    wx.chooseMessageFile({
      count: 1, type: 'file', extension: ['pdf', 'doc', 'docx', 'zip'],
      success(res) { that.setData({ fFile: res.tempFiles[0] }); },
      fail() {}
    });
  },

  submitForm() {
    const title = (this.data.fTitle || '').trim();
    if (!title) { this.setData({ fErr: '请填写标题' }); return; }
    const app = this.data.apps[this.data.appIndex];
    const content = (this.data.fContent || '').trim();
    const that = this;
    this.setData({ saving: true, fErr: '' });

    function afterCreate(body) {
      if (!(body && body.success)) { that.setData({ saving: false, fErr: (body && body.message) || '提交失败' }); return; }
      const id = body.data.id;
      request('/reports/' + id + '/submit', { method: 'PUT' }).then(function () {
        that.setData({ saving: false, showForm: false });
        wx.showToast({ title: '报告已提交', icon: 'success' });
        that.load();
      });
    }

    if (this.data.fFile) {
      uploadFile('/reports', this.data.fFile.path, { application_id: String(app.id), title: title, content: content })
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    } else {
      request('/reports', { method: 'POST', data: { application_id: app.id, title: title, content: content } })
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    }
  },

  openFile(e) {
    const path = e.currentTarget.dataset.path;
    wx.showLoading({ title: '下载中' });
    downloadFile(path, { timeout: 30000 })
      .then(function (res) {
        wx.hideLoading();
        wx.openDocument({ filePath: res.tempFilePath, showMenu: true });
      })
      .catch(function (e) {
        wx.hideLoading();
        wx.showToast({ title: e.message || '下载失败', icon: 'none' });
      });
  }
});
