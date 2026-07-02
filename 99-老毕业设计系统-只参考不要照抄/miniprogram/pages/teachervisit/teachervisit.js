const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

Page({
  data: {
    loading: true, err: '', list: [], students: [],
    showForm: false, stuIdx: 0, visitDate: '', location: '', content: '', problems: '', saving: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([
      get('/benchmark/teacher-visits?page_size=30'),
      get('/intern-stats/process?page_size=50').catch(function () { return { list: [] }; })
    ]).then(function (arr) {
      const list = ((arr[0] && arr[0].list) || []).map(function (v) {
        return Object.assign({}, v, { dateText: fmtDate(v.visit_date) });
      });
      const raw = (arr[1] && arr[1].list) || [];
      const students = raw.map(function (s) {
        return { id: s.student_id || s.id, real_name: s.student_name || s.real_name };
      });
      that.setData({ loading: false, list: list, students: students });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  openForm() {
    const today = new Date().toISOString().slice(0, 10);
    this.setData({ showForm: true, stuIdx: 0, visitDate: today, location: '', content: '', problems: '' });
  },
  closeForm() { this.setData({ showForm: false }); },
  noop() {},
  onStu(e) { this.setData({ stuIdx: Number(e.detail.value) }); },
  onDate(e) { this.setData({ visitDate: e.detail.value }); },
  onLoc(e) { this.setData({ location: e.detail.value }); },
  onContent(e) { this.setData({ content: e.detail.value }); },
  onProb(e) { this.setData({ problems: e.detail.value }); },

  submit() {
    const stu = this.data.students[this.data.stuIdx];
    if (!stu) { wx.showToast({ title: '无指导学生', icon: 'none' }); return; }
    if (!this.data.visitDate) { wx.showToast({ title: '请选择日期', icon: 'none' }); return; }
    const that = this;
    this.setData({ saving: true });
    request('/benchmark/teacher-visits', {
      method: 'POST',
      data: {
        student_id: stu.id,
        visit_date: this.data.visitDate,
        location: this.data.location,
        content: this.data.content,
        problems: this.data.problems
      }
    }).then(function (res) {
      that.setData({ saving: false, showForm: false });
      wx.showToast({ title: res.data && res.data.success ? '已登记' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    }).catch(function (e) { that.setData({ saving: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  }
});
