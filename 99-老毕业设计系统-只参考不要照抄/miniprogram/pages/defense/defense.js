const { get, request } = require('../../utils/request');

const ST = { 0: '筹备', 1: '进行中', 2: '已完成' };
const STC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g' };

Page({
  data: {
    loading: true, err: '', list: [],
    showSheet: false, detailLoading: false, group: null, members: []
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/defense/groups?page_size=40').then(function (d) {
      const list = ((d && d.list) || []).map(function (g) {
        return Object.assign({}, g, { stText: ST[g.status] || '', stClass: STC[g.status] || 'tag-m' });
      });
      that.setData({ loading: false, list: list });
      if (done) done();
    }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); if (done) done(); });
  },

  openGroup(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    this.setData({ showSheet: true, detailLoading: true, group: null, members: [] });
    get('/defense/groups/' + id).then(function (d) {
      const members = ((d && d.members) || []).map(function (m) {
        return Object.assign({}, m, {
          scoreInput: m.my_score != null ? String(m.my_score) : '',
          commentInput: m.my_comment || ''
        });
      });
      that.setData({ detailLoading: false, group: (d && d.group) || null, members: members });
    }).catch(function (err) {
      that.setData({ detailLoading: false });
      wx.showToast({ title: err.message || '加载失败', icon: 'none' });
    });
  },

  closeSheet() { this.setData({ showSheet: false }); },
  noop() {},

  onScore(e) {
    const i = e.currentTarget.dataset.i;
    this.setData({ ['members[' + i + '].scoreInput']: e.detail.value });
  },
  onComment(e) {
    const i = e.currentTarget.dataset.i;
    this.setData({ ['members[' + i + '].commentInput']: e.detail.value });
  },

  saveScore(e) {
    const i = e.currentTarget.dataset.i;
    const m = this.data.members[i];
    const score = Number(m.scoreInput);
    if (!(score >= 0 && score <= 100)) { wx.showToast({ title: '评分需在 0~100', icon: 'none' }); return; }
    request('/defense/groups/' + this.data.group.id + '/students/' + m.student_id + '/score',
      { method: 'PUT', data: { score: score, comment: m.commentInput || '' } })
      .then(function (res) {
        wx.showToast({ title: res.data && res.data.success ? '已保存' : (res.data.message || '失败'), icon: 'none' });
      });
  }
});
