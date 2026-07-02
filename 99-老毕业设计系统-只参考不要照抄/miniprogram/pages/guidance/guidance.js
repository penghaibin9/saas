const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

function today() {
  const d = new Date();
  const m = ('0' + (d.getMonth() + 1)).slice(-2);
  const day = ('0' + d.getDate()).slice(-2);
  return d.getFullYear() + '-' + m + '-' + day;
}

Page({
  data: {
    loading: true, err: '', list: [],
    showForm: false, students: [], stuIndex: 0, fDate: today(), fTitle: '', fContent: '', fErr: '', saving: false,
    showDetail: false, detail: null
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-guidances?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (g) {
        return Object.assign({}, g, { dateText: fmtDate(g.guidance_date || g.create_time) });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  noop() {},

  openForm() {
    const that = this;
    get('/intern-stats/process?page_size=100').then(function (d) {
      const students = ((d && d.list) || []).map(function (s) {
        return { id: s.student_id, label: s.student_name + '（' + (s.student_eeid || '') + '）' };
      });
      if (!students.length) { wx.showToast({ title: '暂无可指导的学生', icon: 'none' }); return; }
      that.setData({ showForm: true, students: students, stuIndex: 0, fDate: today(), fTitle: '', fContent: '', fErr: '' });
    });
  },
  closeForm() { this.setData({ showForm: false }); },
  onStu(e) { this.setData({ stuIndex: Number(e.detail.value) }); },
  onDate(e) { this.setData({ fDate: e.detail.value }); },
  onTitle(e) { this.setData({ fTitle: e.detail.value }); },
  onContent(e) { this.setData({ fContent: e.detail.value }); },

  submitForm() {
    const title = (this.data.fTitle || '').trim();
    if (!title) { this.setData({ fErr: '请填写标题' }); return; }
    const stu = this.data.students[this.data.stuIndex];
    const that = this;
    this.setData({ saving: true, fErr: '' });
    request('/gd-guidances', { method: 'POST', data: { student_id: stu.id, guidance_date: this.data.fDate, title: title, content: (this.data.fContent || '').trim() } })
      .then(function (res) {
        that.setData({ saving: false });
        if (!(res.data && res.data.success)) { that.setData({ fErr: res.data.message || '保存失败' }); return; }
        that.setData({ showForm: false });
        wx.showToast({ title: '已保存', icon: 'success' });
        that.load();
      }).catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
  },

  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  removeItem() {
    const id = this.data.detail.id, that = this;
    wx.showModal({
      title: '删除', content: '确定删除该指导记录？',
      success(r) {
        if (!r.confirm) return;
        request('/gd-guidances/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已删除' : (res.data.message || '失败'), icon: 'none' });
          that.closeDetail(); that.load();
        });
      }
    });
  }
});
