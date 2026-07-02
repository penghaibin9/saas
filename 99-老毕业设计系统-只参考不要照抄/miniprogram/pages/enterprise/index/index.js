const app = getApp();
const { get, request } = require('../../utils/request');

const POS_ST = { 0: '待审核', 1: '已上架', 2: '已下架' };
const POS_C = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-m' };
const APP_ST = { 3: '待确认录用', 5: '已录用', 6: '未录用' };
const APP_C = { 3: 'tag-y', 5: 'tag-g', 6: 'tag-r' };
const INTERN_TYPE_OPTS = ['顶岗实习', '跟岗实习', '认知实习'];
const EDU_OPTS = ['不限', '中专', '大专', '本科', '硕士及以上'];

Page({
  data: {
    loading: true, err: '', tab: 'dash', ent: {}, dash: {},
    positions: [], applications: [], interns: [], checkins: [],
    showPosForm: false, posTitle: '', posDesc: '', posSalary: '', posHead: '1', submitting: false,
    internTypeOpts: INTERN_TYPE_OPTS, eduOpts: EDU_OPTS,
    posInternTypeIdx: 0, posEduIdx: 0, posMajor: '', posWorkTime: '', posWelfare: '', posRegular: false, posDeadline: ''
  },

  onShow() {
    if (!app.globalData.user || app.globalData.user.role !== 5) {
      wx.reLaunch({ url: '/pages/login/login' });
      return;
    }
    this.load();
  },

  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([
      get('/enterprise-portal/me'),
      get('/enterprise-portal/dashboard'),
      get('/enterprise-portal/positions?page_size=50'),
      get('/enterprise-portal/applications?status=3&page_size=50'),
      get('/enterprise-portal/interns?page_size=50'),
      get('/enterprise-portal/checkins?page_size=30')
    ]).then(function (arr) {
      const pos = ((arr[2] && arr[2].list) || []).map(function (p) {
        return Object.assign({}, p, {
          stText: POS_ST[p.status] || '', stClass: POS_C[p.status] || 'tag-m',
          internTypeText: p.intern_type ? INTERN_TYPE_OPTS[p.intern_type - 1] : '',
          welfareList: String(p.welfare || '').split(/[,，;；]+/).map(function (s) { return s.trim(); }).filter(Boolean)
        });
      });
      const apps = ((arr[3] && arr[3].list) || []).map(function (a) {
        return Object.assign({}, a, { stText: APP_ST[a.status] || '', stClass: APP_C[a.status] || 'tag-m' });
      });
      that.setData({
        loading: false, ent: arr[0] || {}, dash: arr[1] || {},
        positions: pos, applications: apps,
        interns: (arr[4] && arr[4].list) || [],
        checkins: (arr[5] && arr[5].list) || []
      });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  setTab(e) { this.setData({ tab: e.currentTarget.dataset.t }); },
  logout() { app.logout(); },

  openPosForm() { this.setData({ showPosForm: true, posTitle: '', posDesc: '', posSalary: '', posHead: '1', posInternTypeIdx: 0, posEduIdx: 0, posMajor: '', posWorkTime: '', posWelfare: '', posRegular: false, posDeadline: '' }); },
  closePosForm() { this.setData({ showPosForm: false }); },
  noop() {},
  onPosTitle(e) { this.setData({ posTitle: e.detail.value }); },
  onPosDesc(e) { this.setData({ posDesc: e.detail.value }); },
  onPosSalary(e) { this.setData({ posSalary: e.detail.value }); },
  onPosHead(e) { this.setData({ posHead: e.detail.value }); },
  onPosInternType(e) { this.setData({ posInternTypeIdx: Number(e.detail.value) }); },
  onPosEdu(e) { this.setData({ posEduIdx: Number(e.detail.value) }); },
  onPosMajor(e) { this.setData({ posMajor: e.detail.value }); },
  onPosWorkTime(e) { this.setData({ posWorkTime: e.detail.value }); },
  onPosWelfare(e) { this.setData({ posWelfare: e.detail.value }); },
  onPosRegular(e) { this.setData({ posRegular: e.detail.value }); },
  onPosDeadline(e) { this.setData({ posDeadline: e.detail.value }); },

  submitPos() {
    const title = (this.data.posTitle || '').trim();
    if (!title) { wx.showToast({ title: '请填写岗位名称', icon: 'none' }); return; }
    this.setData({ submitting: true });
    const that = this;
    request('/enterprise-portal/positions', {
      method: 'POST',
      data: {
        title: title,
        description: (this.data.posDesc || '').trim(),
        salary: (this.data.posSalary || '').trim(),
        headcount: Number(this.data.posHead) || 1,
        intern_type: this.data.posInternTypeIdx + 1,
        edu_req: EDU_OPTS[this.data.posEduIdx] === '不限' ? '' : EDU_OPTS[this.data.posEduIdx],
        major_req: (this.data.posMajor || '').trim(),
        work_time: (this.data.posWorkTime || '').trim(),
        welfare: (this.data.posWelfare || '').trim(),
        to_regular: this.data.posRegular ? 1 : 0,
        deadline: this.data.posDeadline || null
      }
    }).then(function (res) {
      that.setData({ submitting: false, showPosForm: false });
      wx.showToast({ title: (res.data && res.data.message) || '已提交', icon: 'none' });
      that.load();
    }).catch(function (e) {
      that.setData({ submitting: false });
      wx.showToast({ title: e.message || '提交失败', icon: 'none' });
    });
  },

  confirmHire(e) {
    const id = e.currentTarget.dataset.id;
    const hired = e.currentTarget.dataset.hired === '1';
    const that = this;
    wx.showModal({
      title: hired ? '确认录用' : '确认不录用',
      content: hired ? '确定录用该学生？' : '确定标记为不录用？',
      success(r) {
        if (!r.confirm) return;
        request('/enterprise-portal/applications/' + id + '/confirm', {
          method: 'PUT', data: { hired: hired }
        }).then(function (res) {
          wx.showToast({ title: (res.data && res.data.message) || '已操作', icon: 'none' });
          that.load();
        }).catch(function (err) {
          wx.showToast({ title: err.message || '操作失败', icon: 'none' });
        });
      }
    });
  }
});
