const { get, request } = require('../../utils/request');

const APP_ST = { 0: '待审核', 1: '教师同意', 2: '教师拒绝', 3: '院校通过', 4: '院校拒绝', 5: '已录用', 6: '未录用' };
const INTERN_TYPE = { 1: '顶岗实习', 2: '跟岗实习', 3: '认知实习' };

// 富化岗位：补充商用展示字段（实习类型 / 福利 chips / 报名截止）
function enrichPos(p) {
  const welfareList = String(p.welfare || '').split(/[,，;；]+/).map(function (s) { return s.trim(); }).filter(Boolean);
  return Object.assign({}, p, {
    internTypeText: INTERN_TYPE[p.intern_type] || '',
    welfareList: welfareList,
    deadlineText: p.deadline ? String(p.deadline).slice(0, 10) : ''
  });
}

Page({
  data: { loading: true, err: '', list: [], recommend: [], hasTags: true, showDetail: false, detail: null },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([
      get('/positions?status=1&page_size=30'),
      get('/applications?page_size=50'),
      get('/positions/recommend?limit=5').catch(function () { return null; })
    ])
      .then(function (arr) {
        const applied = {};
        ((arr[1] && arr[1].list) || []).forEach(function (a) { applied[a.position_id] = a.status; });
        const list = ((arr[0] && arr[0].list) || []).map(function (p) {
          const e = enrichPos(p);
          e.appliedText = applied[p.position_id] != null || applied[p.id] != null ? (APP_ST[applied[p.id]] || '已申请') : '';
          return e;
        });
        const rec = arr[2] || {};
        const recommend = ((rec.list) || []).filter(function (p) { return p.match_score > 0; }).slice(0, 5)
          .map(function (p) { const e = enrichPos(p); e.tagsText = (p.match_tags || []).join(' · '); return e; });
        that.setData({ loading: false, list: list, recommend: recommend, hasTags: rec.hasTags !== false });
        if (done) done();
      })
      .catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  noop() {},
  openDetail(e) { this.setData({ showDetail: true, detail: e.currentTarget.dataset.item }); },
  closeDetail() { this.setData({ showDetail: false, detail: null }); },

  apply(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    wx.showModal({
      title: '申请实习岗位', editable: true, placeholderText: '申请说明（可选）',
      success(r) {
        if (!r.confirm) return;
        request('/applications', { method: 'POST', data: { position_id: id, student_remark: (r.content || '').trim() } })
          .then(function (res) {
            wx.showToast({ title: res.data && res.data.success ? '申请已提交' : (res.data.message || '失败'), icon: 'none' });
            that.setData({ showDetail: false });
            that.load();
          });
      }
    });
  },

  toApplications() { wx.navigateTo({ url: '/pages/applications/applications' }); }
});
