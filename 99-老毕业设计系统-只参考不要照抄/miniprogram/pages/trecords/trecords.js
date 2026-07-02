const { get, request, uploadFile } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const ST = { 0: '草稿', 1: '已提交' };
const STC = { 0: 'tag-m', 1: 'tag-g' };

function today() {
  const d = new Date();
  const m = ('0' + (d.getMonth() + 1)).slice(-2);
  const day = ('0' + d.getDate()).slice(-2);
  return d.getFullYear() + '-' + m + '-' + day;
}

Page({
  data: {
    loading: true, err: '', list: [],
    showForm: false, type: 'monthly', students: [], stuIndex: 0,
    fDate: today(), fTitle: '', fContent: '', fFile: null, fErr: '', saving: false,
    showDetail: false, detail: null
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/teacher-records?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (r) {
        return Object.assign({}, r, {
          dateText: fmtDate(r.record_date || r.create_time),
          typeText: r.type === 'visit' ? '[走访] ' : '[月报] ',
          statusText: ST[r.status] || '', statusClass: STC[r.status] || 'tag-m'
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  noop() {},

  openForm() {
    const that = this;
    get('/intern-stats/process?page_size=100').then(function (d) {
      const students = [{ id: '', label: '不关联学生' }].concat(((d && d.list) || []).map(function (s) {
        return { id: s.student_id, label: s.student_name + '（' + (s.student_eeid || '') + '）' };
      }));
      that.setData({ showForm: true, type: 'monthly', students: students, stuIndex: 0, fDate: today(), fTitle: '', fContent: '', fFile: null, fErr: '' });
    });
  },
  closeForm() { this.setData({ showForm: false }); },
  setType(e) { this.setData({ type: e.currentTarget.dataset.t }); },
  onStu(e) { this.setData({ stuIndex: Number(e.detail.value) }); },
  onDate(e) { this.setData({ fDate: e.detail.value }); },
  onTitle(e) { this.setData({ fTitle: e.detail.value }); },
  onContent(e) { this.setData({ fContent: e.detail.value }); },
  chooseFile() {
    const that = this;
    wx.chooseMessageFile({ count: 1, type: 'file', success(res) { that.setData({ fFile: res.tempFiles[0] }); }, fail() {} });
  },

  submitForm() {
    const title = (this.data.fTitle || '').trim();
    if (!title) { this.setData({ fErr: '请填写标题' }); return; }
    const that = this;
    const stu = this.data.students[this.data.stuIndex];
    const fd = { type: this.data.type, title: title, content: (this.data.fContent || '').trim(), record_date: this.data.fDate };
    if (stu && stu.id) fd.student_id = String(stu.id);
    this.setData({ saving: true, fErr: '' });

    const afterCreate = function (body) {
      if (!(body && body.success)) { that.setData({ saving: false, fErr: (body && body.message) || '保存失败' }); return; }
      request('/teacher-records/' + body.data.id + '/submit', { method: 'PUT' }).then(function () {
        that.setData({ saving: false, showForm: false });
        wx.showToast({ title: '已提交', icon: 'success' });
        that.load();
      });
    };

    if (this.data.fFile) {
      uploadFile('/teacher-records', this.data.fFile.path, fd, 'file')
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    } else {
      request('/teacher-records', { method: 'POST', data: fd })
        .then(function (res) { afterCreate(res.data); })
        .catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
    }
  },

  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  removeItem() {
    const id = this.data.detail.id, that = this;
    wx.showModal({
      title: '删除', content: '确定删除该记录？',
      success(r) {
        if (!r.confirm) return;
        request('/teacher-records/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已删除' : (res.data.message || '失败'), icon: 'none' });
          that.closeDetail(); that.load();
        });
      }
    });
  }
});
