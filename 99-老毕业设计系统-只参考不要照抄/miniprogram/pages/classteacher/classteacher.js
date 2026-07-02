const { get, request } = require('../../utils/request');

Page({
  data: {
    loading: true, err: '', students: [],
    noCheckin: [], noWeekly: [], noConsent: [], noAppraisal: [],
    urging: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/benchmark/class-teacher/dashboard').then(function (d) {
      const urge = (d && d.urge) || {};
      that.setData({
        loading: false,
        students: (d && d.students) || [],
        noCheckin: urge.noCheckin || [],
        noWeekly: urge.noWeekly || [],
        noConsent: urge.noConsent || [],
        noAppraisal: urge.noAppraisal || []
      });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  goUrge() {
    wx.navigateTo({ url: '/pages/urgehub/urgehub' });
  },

  goStudents() {
    wx.switchTab({ url: '/pages/students/students' });
  },

  goParentConsent() {
    wx.navigateTo({ url: '/pages/parentconsent/parentconsent' });
  },

  goAppraisal() {
    wx.navigateTo({ url: '/pages/appraisal/appraisal' });
  },

  goCheckinUrge() {
    wx.navigateTo({ url: '/pages/urgehub/urgehub' });
  },

  urge(e) {
    const kind = e.currentTarget.dataset.kind;
    const map = {
      noCheckin: { list: this.data.noCheckin, title: '打卡催办', content: '请及时完成今日实习打卡' },
      noWeekly: { list: this.data.noWeekly, title: '周报催办', content: '请及时提交实习周报' }
    };
    const cfg = map[kind];
    if (!cfg || !cfg.list.length) {
      wx.showToast({ title: '暂无待催办', icon: 'none' }); return;
    }
    const ids = cfg.list.map(function (x) { return x.student_id; }).filter(Boolean);
    const that = this;
    request('/benchmark/urge-notify', {
      method: 'POST',
      data: { student_ids: ids, title: cfg.title, content: cfg.content }
    }).then(function (res) {
      wx.showToast({ title: res.data && res.data.success ? '已发送' : (res.data.message || '失败'), icon: 'none' });
    }).catch(function (err) { wx.showToast({ title: err.message, icon: 'none' }); });
  }
});
