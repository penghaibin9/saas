const { get, request, uploadFile } = require('../../utils/request');

const DRAFT_KEY = 'newlog_draft';
const MIN_LEN = 30;

Page({
  data: {
    id: null,
    type: 'weekly',
    title: '',
    content: '',
    contentLen: 0,
    minLen: MIN_LEN,
    file: null,
    err: '',
    saving: false,
    savingDraft: false,
    draftSavedAt: ''
  },

  chooseFile() {
    const that = this;
    wx.chooseMessageFile({
      count: 1, type: 'file',
      success(res) { that.setData({ file: res.tempFiles[0] }); },
      fail() {}
    });
  },

  onLoad(q) {
    if (q && q.id) {
      const that = this;
      this.setData({ id: q.id });
      wx.setNavigationBarTitle({ title: '编辑周报/月报' });
      get('/intern-logs/' + q.id).then(function (l) {
        if (l) that.setData({ type: l.type || 'weekly', title: l.title || '', content: l.content || '', contentLen: (l.content || '').length });
      }).catch(function () {});
      return;
    }
    // 新建：恢复本地暂存草稿
    const draft = wx.getStorageSync(DRAFT_KEY);
    if (draft && (draft.title || draft.content)) {
      this.setData({
        type: draft.type || 'weekly',
        title: draft.title || '',
        content: draft.content || '',
        contentLen: (draft.content || '').length
      });
      wx.showToast({ title: '已恢复上次草稿', icon: 'none' });
    }
  },

  // 输入防抖自动暂存（仅新建模式）
  _autoSave() {
    if (this.data.id) return;
    const that = this;
    clearTimeout(this._draftTimer);
    this._draftTimer = setTimeout(function () {
      wx.setStorageSync(DRAFT_KEY, { type: that.data.type, title: that.data.title, content: that.data.content });
      const n = new Date();
      const p = function (x) { return x < 10 ? '0' + x : x; };
      that.setData({ draftSavedAt: p(n.getHours()) + ':' + p(n.getMinutes()) });
    }, 800);
  },

  clearDraft() {
    if (!this.data.id) wx.removeStorageSync(DRAFT_KEY);
  },

  cancel() { wx.navigateBack(); },
  setType(e) { this.setData({ type: e.currentTarget.dataset.t }); this._autoSave(); },

  // 套用学校配置的周报/月报模板（内容为空或确认后填入）
  useTemplate() {
    const that = this;
    const apply = function () {
      get('/intern-logs/template?type=' + that.data.type).then(function (d) {
        if (d && d.template) {
          that.setData({ content: d.template, contentLen: d.template.length });
          that._autoSave();
        }
      }).catch(function () {});
    };
    if ((this.data.content || '').trim()) {
      wx.showModal({ title: '套用模板', content: '将覆盖当前内容,确定?', success(r) { if (r.confirm) apply(); } });
    } else { apply(); }
  },
  onTitle(e) { this.setData({ title: e.detail.value }); this._autoSave(); },
  onContent(e) { this.setData({ content: e.detail.value, contentLen: (e.detail.value || '').length }); this._autoSave(); },

  validate(forSubmit) {
    const title = (this.data.title || '').trim();
    const content = (this.data.content || '').trim();
    if (!title) { this.setData({ err: '请填写标题' }); return null; }
    if (forSubmit && content.length < MIN_LEN) {
      this.setData({ err: '内容不少于 ' + MIN_LEN + ' 字才能提交批阅，可先保存草稿' });
      return null;
    }
    this.setData({ err: '' });
    return { type: this.data.type, title: title, content: content };
  },

  // 仅保存草稿（不进入批阅流）
  saveDraft() {
    const body = this.validate(false);
    if (!body) return;
    const that = this;
    this.setData({ savingDraft: true });
    const onDone = function (ok, msg) {
      that.setData({ savingDraft: false });
      if (!ok) { that.setData({ err: msg || '保存失败' }); return; }
      that.clearDraft();
      wx.showToast({ title: '草稿已保存', icon: 'success' });
      setTimeout(function () { wx.navigateBack(); }, 600);
    };
    if (this.data.id) {
      request('/intern-logs/' + this.data.id, { method: 'PUT', data: body })
        .then(function (res) { onDone(res.data && res.data.success, res.data && res.data.message); })
        .catch(function (e) { onDone(false, e.message); });
    } else if (this.data.file) {
      uploadFile('/intern-logs', this.data.file.path, { type: body.type, title: body.title, content: body.content }, 'file')
        .then(function (res) { onDone(res.data && res.data.success, res.data && res.data.message); })
        .catch(function (e) { onDone(false, e.message); });
    } else {
      request('/intern-logs', { method: 'POST', data: body })
        .then(function (res) { onDone(res.data && res.data.success, res.data && res.data.message); })
        .catch(function (e) { onDone(false, e.message); });
    }
  },

  // 提交批阅
  submit() {
    const body = this.validate(true);
    if (!body) return;
    const that = this;
    this.setData({ saving: true });
    const fail = function (msg) { that.setData({ saving: false, err: msg || '提交失败' }); };
    const submitById = function (id) {
      request('/intern-logs/' + id + '/submit', { method: 'PUT' }).then(function () {
        that.setData({ saving: false });
        that.clearDraft();
        wx.showToast({ title: '已提交批阅', icon: 'success' });
        setTimeout(function () { wx.navigateBack(); }, 600);
      }).catch(function (e) { fail(e.message); });
    };

    if (this.data.id) {
      // 编辑：先保存再提交
      request('/intern-logs/' + this.data.id, { method: 'PUT', data: body }).then(function (res) {
        if (!(res.data && res.data.success)) { fail(res.data && res.data.message); return; }
        submitById(that.data.id);
      }).catch(function (e) { fail(e.message); });
      return;
    }

    const afterCreate = function (resData) {
      if (!(resData && resData.success)) { fail(resData && resData.message); return; }
      submitById(resData.data.id);
    };
    if (this.data.file) {
      uploadFile('/intern-logs', this.data.file.path, { type: body.type, title: body.title, content: body.content }, 'file')
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { fail(e.message); });
    } else {
      request('/intern-logs', { method: 'POST', data: body })
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { fail(e.message); });
    }
  }
});
