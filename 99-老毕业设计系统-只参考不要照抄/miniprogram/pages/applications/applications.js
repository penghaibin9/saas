const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const APP_ST = { 0: '待审核', 1: '教师同意', 2: '教师拒绝', 3: '院校通过', 4: '院校拒绝', 5: '已录用', 6: '未录用' };
const APP_STC = { 0: 'tag-y', 1: 'tag-b', 2: 'tag-r', 3: 'tag-g', 4: 'tag-r', 5: 'tag-g', 6: 'tag-m' };

// 投递进度时间轴：提交 → 教师审核 → 院校审核 → 企业录用
function buildSteps(status) {
  function node(label, state) { return { label: label, state: state, mark: state === 'done' ? '✓' : state === 'reject' ? '✕' : '' }; }
  const teacher = status === 2 ? 'reject' : (status >= 1 ? 'done' : 'current');
  const school = status === 4 ? 'reject' : (status >= 3 ? 'done' : (status === 1 ? 'current' : 'todo'));
  const hire = status === 6 ? 'reject' : (status === 5 ? 'done' : (status === 3 ? 'current' : 'todo'));
  return [node('提交申请', 'done'), node('教师审核', teacher), node('院校审核', school), node('企业录用', hire)];
}

Page({
  data: { loading: true, err: '', list: [] },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/applications?page_size=30').then(function (d) {
      const list = ((d && d.list) || []).map(function (a) {
        return Object.assign({}, a, {
          dateText: fmtDate(a.apply_time),
          statusText: APP_ST[a.status] || '',
          statusClass: APP_STC[a.status] || 'tag-m',
          steps: buildSteps(a.status)
        });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  toPositions() { wx.navigateTo({ url: '/pages/positions/positions' }); },

  withdraw(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    wx.showModal({
      title: '撤回申请', content: '确定撤回该申请？',
      success(r) {
        if (!r.confirm) return;
        request('/applications/' + id, { method: 'DELETE' }).then(function (res) {
          wx.showToast({ title: res.data && res.data.success ? '已撤回' : (res.data.message || '失败'), icon: 'none' });
          that.load();
        });
      }
    });
  }
});
