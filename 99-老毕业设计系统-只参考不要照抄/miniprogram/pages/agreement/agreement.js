const { get, request } = require('../../utils/request');
const app = getApp();

const ST = { 0: '待签署', 1: '签署中', 2: '已生效', 3: '已作废' };
const STC = { 0: 'tag-y', 1: 'tag-m', 2: 'tag-g', 3: 'tag-r' };

Page({
  data: { loading: true, err: '', list: [], isTeacher: false },

  onShow() { this.setData({ isTeacher: app.isTeacher() }); this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    const isTeacher = app.isTeacher();
    this.setData({ loading: true, err: '' });
    get('/agreements?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (a) {
        return Object.assign({}, a, {
          statusText: ST[a.status] || '', statusClass: STC[a.status] || 'tag-m',
          canSign: !isTeacher && !a.student_signed && a.status !== 2 && a.status !== 3,
          canCosign: isTeacher && a.student_signed && !a.teacher_signed && a.status !== 3
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  detail(e) {
    const a = e.currentTarget.dataset.item;
    if (!a) return;
    const lines = [
      '企业：' + (a.enterprise_name || '-'),
      '岗位：' + (a.position_title || '-'),
      '指导教师：' + (a.teacher_name || '-'),
      '实习期：' + (a.start_date || '-') + ' 至 ' + (a.end_date || '-'),
      '状态：' + (ST[a.status] || ''),
      '',
      (a.content || '（无条款正文）'),
      '',
      '学生签署：' + (a.student_signed ? '已签' : '未签'),
      '教师会签：' + (a.teacher_signed ? '已签' : '未签'),
      '校方盖章：' + (a.school_signed ? '已盖章' : '未盖章')
    ];
    wx.showModal({ title: a.title, content: lines.join('\n'), showCancel: false, confirmText: '关闭' });
  },

  sign(e) {
    const id = e.currentTarget.dataset.id, that = this;
    const defName = (app.globalData.user && app.globalData.user.realName) || '';
    wx.showModal({
      title: '签署实习协议', editable: true, placeholderText: '请输入本人姓名确认签署', content: defName,
      success(r) {
        if (!r.confirm) return;
        request('/agreements/' + id + '/student-sign', { method: 'PUT', data: { sign_name: (r.content || defName) } })
          .then(function (res) {
            wx.showToast({ title: res.data && res.data.success ? '签署成功' : (res.data.message || '失败'), icon: 'none' });
            that.load();
          });
      }
    });
  },

  cosign(e) {
    const id = e.currentTarget.dataset.id, that = this;
    wx.showModal({
      title: '教师会签', content: '确认对该协议进行会签？',
      success(r) {
        if (!r.confirm) return;
        request('/agreements/' + id + '/teacher-sign', { method: 'PUT', data: {} })
          .then(function (res) {
            wx.showToast({ title: res.data && res.data.success ? '会签成功' : (res.data.message || '失败'), icon: 'none' });
            that.load();
          });
      }
    });
  }
});
