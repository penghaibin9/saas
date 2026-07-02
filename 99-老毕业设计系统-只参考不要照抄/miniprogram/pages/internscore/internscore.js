const { get, request } = require('../../utils/request');
const app = getApp();

Page({
  data: {
    loading: true, err: '', score: null, config: null,
    isTeacher: false, computing: false, publishing: false,
    students: [], stuIdx: 0, published: false,
    schoolScoreInput: ''
  },

  onSchoolScore(e) { this.setData({ schoolScoreInput: e.detail.value }); },

  onShow() {
    this.setData({ isTeacher: app.isTeacher() });
    this.load();
  },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    const reqs = [];
    if (app.isTeacher()) {
      reqs.push(Promise.resolve(null));
    } else {
      reqs.push(get('/benchmark/intern-scores/mine').catch(function () { return null; }));
    }
    reqs.push(get('/benchmark/intern-score-config').catch(function () { return null; }));
    if (app.isTeacher()) {
      reqs.push(get('/intern-stats/process?page_size=50').catch(function () { return { list: [] }; }));
    }
    Promise.all(reqs).then(function (arr) {
      const raw = (arr[2] && arr[2].list) || [];
      const students = raw.map(function (s) {
        return { id: s.student_id || s.id, real_name: s.student_name || s.real_name };
      });
      that.setData({
        loading: false,
        score: arr[0],
        config: arr[1] || null,
        published: arr[0] && arr[0].published === 1,
        students: students,
        stuIdx: 0
      });
      if (app.isTeacher() && students.length) that.loadStudentScore(0);
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  onStu(e) {
    this.setData({ stuIdx: Number(e.detail.value) });
    if (this.data.isTeacher) this.loadStudentScore(Number(e.detail.value));
  },

  loadStudentScore(idx) {
    const i = idx != null ? idx : this.data.stuIdx;
    const stu = this.data.students[i];
    if (!stu) return;
    const that = this;
    get('/benchmark/intern-scores/mine?student_id=' + stu.id).then(function (s) {
      that.setData({ score: s, published: s && s.published === 1 });
    }).catch(function () {
      that.setData({ score: null, published: false });
    });
  },

  compute() {
    const that = this;
    this.setData({ computing: true });
    const stu = this.data.isTeacher && this.data.students[this.data.stuIdx];
    const url = stu ? '/benchmark/intern-scores/compute?student_id=' + stu.id : '/benchmark/intern-scores/compute';
    const body = {};
    if (this.data.schoolScoreInput !== '' && this.data.schoolScoreInput != null) {
      body.school_score = Number(this.data.schoolScoreInput);
    }
    request(url, { method: 'POST', data: body }).then(function (res) {
      that.setData({ computing: false });
      if (res.data && res.data.success) {
        const d = res.data.data || {};
        const incomplete = d.incomplete === 1 || (d.missing && d.missing.length);
        wx.showToast({ title: incomplete ? '已核算(有缺项)' : '已核算', icon: incomplete ? 'none' : 'success' });
        that.setData({ score: d, published: d.published === 1 });
      } else {
        wx.showToast({ title: (res.data && res.data.message) || '失败', icon: 'none' });
      }
    }).catch(function (e) { that.setData({ computing: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  },

  publish() {
    let sid = null;
    if (this.data.isTeacher) {
      const stu = this.data.students[this.data.stuIdx];
      if (!stu) { wx.showToast({ title: '请选择学生', icon: 'none' }); return; }
      sid = stu.id;
    }
    if (!sid && !this.data.isTeacher) sid = getApp().globalData.user && getApp().globalData.user.id;
    if (!sid) return;
    const that = this;
    wx.showModal({
      title: '发布成绩', content: '发布后学生可见综合考评成绩',
      success(r) {
        if (!r.confirm) return;
        that.setData({ publishing: true });
        request('/benchmark/intern-scores/' + sid + '/publish', { method: 'PUT', data: {} }).then(function (res) {
          that.setData({ publishing: false, published: true });
          wx.showToast({ title: res.data && res.data.success ? '已发布' : (res.data.message || '失败'), icon: 'none' });
          that.load();
        }).catch(function (e) { that.setData({ publishing: false }); wx.showToast({ title: e.message, icon: 'none' }); });
      }
    });
  }
});
