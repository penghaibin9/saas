const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');
const app = getApp();

Page({
  data: {
    loading: true, err: '', list: [], isTeacher: false,
    students: [], showForm: false, stuIdx: 0, fTitle: '', fContent: '', saving: false
  },

  onShow() {
    this.setData({ isTeacher: app.isTeacher() });
    this.load();
  },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    const reqs = [get('/benchmark/task-books?page_size=30')];
    if (app.isTeacher()) {
      reqs.push(get('/intern-stats/process?page_size=50').catch(function () { return { list: [] }; }));
    }
    Promise.all(reqs).then(function (arr) {
      const list = ((arr[0] && arr[0].list) || []).map(function (tb) {
        return Object.assign({}, tb, {
          dateText: fmtDate(tb.update_time || tb.create_time),
          confirmed: tb.student_confirmed === 1,
          canConfirm: tb.student_confirmed !== 1
        });
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

  detail(e) {
    const tb = e.currentTarget.dataset.item;
    if (!tb) return;
    wx.showModal({
      title: tb.title || '任务书',
      content: [
        '学生：' + (tb.student_name || '-'),
        '指导教师：' + (tb.teacher_name || '-'),
        '状态：' + (tb.student_confirmed ? '已确认' : '待确认'),
        '',
        tb.content || '（无正文）'
      ].join('\n'),
      showCancel: false
    });
  },

  openForm() {
    if (!this.data.students.length) {
      wx.showToast({ title: '暂无指导学生', icon: 'none' }); return;
    }
    this.setData({ showForm: true, stuIdx: 0, fTitle: '', fContent: '' });
  },
  closeForm() { this.setData({ showForm: false }); },
  noop() {},
  onStu(e) { this.setData({ stuIdx: Number(e.detail.value) }); },
  onTitle(e) { this.setData({ fTitle: e.detail.value }); },
  onContent(e) { this.setData({ fContent: e.detail.value }); },

  issue() {
    const stu = this.data.students[this.data.stuIdx];
    const title = (this.data.fTitle || '').trim();
    if (!stu) { wx.showToast({ title: '请选择学生', icon: 'none' }); return; }
    if (!title) { wx.showToast({ title: '请填写标题', icon: 'none' }); return; }
    const that = this;
    this.setData({ saving: true });
    request('/benchmark/task-books', {
      method: 'POST',
      data: { student_id: stu.id, title: title, content: this.data.fContent || '' }
    }).then(function (res) {
      that.setData({ saving: false, showForm: false });
      wx.showToast({ title: res.data && res.data.success ? '已下达' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    }).catch(function (e) { that.setData({ saving: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  },

  confirm() {
    const that = this;
    wx.showModal({
      title: '确认任务书', content: '确认后将视为接受任务书内容，是否继续？',
      success(r) {
        if (!r.confirm) return;
        request('/benchmark/task-books/confirm', { method: 'PUT', data: {} }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已确认' : (res.data.message || '失败'), icon: 'none' });
          that.load();
        });
      }
    });
  }
});
