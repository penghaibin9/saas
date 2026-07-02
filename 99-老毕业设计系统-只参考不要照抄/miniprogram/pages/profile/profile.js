const app = getApp();
const { get, request } = require('../../utils/request');

Page({
  data: {
    force: false,
    loading: true,
    err: '',
    u: {},
    name: '',
    phone: '',
    email: '',
    skillTags: '',
    emergencyName: '', emergencyPhone: '', emergencyRelation: '',
    isStudent: false,
    pErr: '',
    saving: false,
    // 改密
    oldPwd: '',
    newPwd: '',
    newPwd2: '',
    cErr: '',
    changing: false
  },

  onLoad(q) {
    const force = !!(q && q.force);
    this.setData({ force: force });
    if (force) wx.setNavigationBarTitle({ title: '修改初始密码' });
    this.load();
  },

  load() {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/users/profile').then(function (u) {
      u = u || app.globalData.user || {};
      that.setData({
        loading: false, u: u,
        name: u.realName || '', phone: u.phone || '', email: u.email || '',
        skillTags: u.skillTags || '', isStudent: !app.isTeacher(),
        emergencyName: u.emergencyName || '', emergencyPhone: u.emergencyPhone || '',
        emergencyRelation: u.emergencyRelation || ''
      });
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败', u: app.globalData.user || {} });
    });
  },

  onName(e) { this.setData({ name: e.detail.value }); },
  onPhone(e) { this.setData({ phone: e.detail.value }); },
  onEmail(e) { this.setData({ email: e.detail.value }); },
  onSkillTags(e) { this.setData({ skillTags: e.detail.value }); },
  onEmName(e) { this.setData({ emergencyName: e.detail.value }); },
  onEmPhone(e) { this.setData({ emergencyPhone: e.detail.value }); },
  onEmRel(e) { this.setData({ emergencyRelation: e.detail.value }); },

  saveProfile() {
    const name = (this.data.name || '').trim();
    const phone = (this.data.phone || '').trim();
    const email = (this.data.email || '').trim();
    const skillTags = (this.data.skillTags || '').trim();
    if (!name) { this.setData({ pErr: '姓名不能为空' }); return; }
    if (phone && !/^1[3-9]\d{9}$/.test(phone)) { this.setData({ pErr: '手机号格式不正确' }); return; }
    if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { this.setData({ pErr: '邮箱格式不正确' }); return; }
    const ep = (this.data.emergencyPhone || '').trim();
    if (ep && !/^1[3-9]\d{9}$/.test(ep)) { this.setData({ pErr: '紧急联系人电话格式不正确' }); return; }
    this.setData({ saving: true, pErr: '' });
    const that = this;
    const payload = { real_name: name, phone: phone, email: email };
    if (this.data.isStudent) {
      payload.skill_tags = skillTags;
      payload.emergency_name = (this.data.emergencyName || '').trim();
      payload.emergency_phone = ep;
      payload.emergency_relation = (this.data.emergencyRelation || '').trim();
    }
    request('/users/profile', { method: 'PUT', data: payload })
      .then(function (res) {
        that.setData({ saving: false });
        if (!(res.data && res.data.success)) { that.setData({ pErr: res.data.message || '保存失败' }); return; }
        const u = Object.assign({}, app.globalData.user, { realName: name, phone: phone, email: email, skillTags: skillTags });
        app.setUser(u);
        wx.showToast({ title: '已保存', icon: 'success' });
      })
      .catch(function (e) { that.setData({ saving: false, pErr: e.message }); });
  },

  onOld(e) { this.setData({ oldPwd: e.detail.value }); },
  onNew(e) { this.setData({ newPwd: e.detail.value }); },
  onNew2(e) { this.setData({ newPwd2: e.detail.value }); },

  changePwd() {
    const op = this.data.oldPwd, np = this.data.newPwd, np2 = this.data.newPwd2;
    if (!op || !np) { this.setData({ cErr: '请填写完整' }); return; }
    if (np !== np2) { this.setData({ cErr: '两次输入的新密码不一致' }); return; }
    if (np.length < 6 || !/[a-zA-Z]/.test(np) || !/[0-9]/.test(np)) { this.setData({ cErr: '新密码需≥6位且含字母和数字' }); return; }
    this.setData({ changing: true, cErr: '' });
    const that = this;
    request('/users/change-password', { method: 'PUT', data: { oldPassword: op, newPassword: np } })
      .then(function (res) {
        that.setData({ changing: false });
        if (!(res.data && res.data.success)) { that.setData({ cErr: res.data.message || '修改失败' }); return; }
        if (res.data.data && res.data.data.token) app.setToken(res.data.data.token);
        const u = Object.assign({}, app.globalData.user, { mustChangePassword: false });
        app.setUser(u);
        that.setData({ oldPwd: '', newPwd: '', newPwd2: '' });
        wx.showToast({ title: '密码已修改', icon: 'success' });
        if (that.data.force) {
          setTimeout(function () { wx.switchTab({ url: '/pages/home/home' }); }, 700);
        }
      })
      .catch(function (e) { that.setData({ changing: false, cErr: e.message }); });
  }
});
