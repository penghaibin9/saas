const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');
const app = getApp();

const RST = { 0: '未开始', 1: '进行中', 2: '已结束' };
const RSTC = { 0: 'tag-m', 1: 'tag-y', 2: 'tag-g' };
const CST = { 0: '待匹配', 1: '已中选', 2: '未中选' };
const CSTC = { 0: 'tag-y', 1: 'tag-g', 2: 'tag-r' };

Page({
  data: {
    loading: true, err: '', rounds: [], pool: [], activeRound: null, isTeacher: false,
    myChoices: [], matched: false,
    showForm: false, picks: ['', '', ''], pickLabels: ['请选择课题', '可选', '可选'], fErr: '', saving: false,
    showPoolForm: false, poolTitle: '', poolQuota: '1', poolDesc: '', poolSaving: false
  },

  onShow() {
    this.setData({ isTeacher: app.isTeacher() });
    this.load();
  },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([
      get('/benchmark/topic-rounds'),
      get('/benchmark/topic-pool')
    ]).then(function (arr) {
      const rounds = ((arr[0] && arr[0].list) || []).map(function (r) {
        return Object.assign({}, r, {
          stText: RST[r.status] || '', stClass: RSTC[r.status] || 'tag-m',
          rangeText: fmtDate(r.start_time) + ' ~ ' + fmtDate(r.end_time)
        });
      });
      const pool = (arr[1] && arr[1].list) || [];
      const active = rounds.find(function (r) { return r.status === 1; }) || rounds[0] || null;
      that.setData({ loading: false, rounds: rounds, pool: pool, activeRound: active });
      // 学生端:加载我在该轮次的志愿与匹配结果
      if (!that.data.isTeacher && active) {
        get('/benchmark/topic-rounds/' + active.id + '/choices').then(function (r) {
          const mine = ((r && r.list) || []).map(function (c) {
            return Object.assign({}, c, { cstText: CST[c.status] || '待匹配', cstClass: CSTC[c.status] || 'tag-m' });
          });
          that.setData({ myChoices: mine, matched: mine.some(function (c) { return c.status === 1; }) });
        }).catch(function () { that.setData({ myChoices: [] }); });
      } else {
        that.setData({ myChoices: [] });
      }
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  openForm() {
    const r = this.data.activeRound;
    if (!r || r.status !== 1) {
      wx.showToast({ title: '当前无进行中的选题轮次', icon: 'none' }); return;
    }
    this.setData({ showForm: true, picks: ['', '', ''], pickLabels: ['请选择课题', '可选', '可选'], fErr: '' });
  },
  closeForm() { this.setData({ showForm: false }); },
  openPoolForm() { this.setData({ showPoolForm: true, poolTitle: '', poolQuota: '1', poolDesc: '' }); },
  closePoolForm() { this.setData({ showPoolForm: false }); },
  noop() {},
  onPick(e) {
    const i = e.currentTarget.dataset.i;
    const idx = Number(e.detail.value);
    const p = this.data.pool[idx];
    if (!p) return;
    const picks = this.data.picks.slice();
    const pickLabels = this.data.pickLabels.slice();
    picks[i] = String(p.id);
    pickLabels[i] = p.title + ' · ' + (p.teacher_name || '');
    this.setData({ picks: picks, pickLabels: pickLabels });
  },
  onPoolTitle(e) { this.setData({ poolTitle: e.detail.value }); },
  onPoolQuota(e) { this.setData({ poolQuota: e.detail.value }); },
  onPoolDesc(e) { this.setData({ poolDesc: e.detail.value }); },

  publishPool() {
    const title = (this.data.poolTitle || '').trim();
    if (!title) { wx.showToast({ title: '请填写课题名称', icon: 'none' }); return; }
    const that = this;
    this.setData({ poolSaving: true });
    request('/benchmark/topic-pool', {
      method: 'POST',
      data: { title: title, quota: Number(this.data.poolQuota) || 1, description: this.data.poolDesc || '' }
    }).then(function (res) {
      that.setData({ poolSaving: false, showPoolForm: false });
      wx.showToast({ title: res.data && res.data.success ? '课题已发布' : (res.data.message || '失败'), icon: 'none' });
      that.load();
    }).catch(function (e) { that.setData({ poolSaving: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  },

  submitChoices() {
    const round = this.data.activeRound;
    const choices = [];
    this.data.picks.forEach(function (pid, i) {
      if (pid) choices.push({ pool_id: Number(pid), priority: i + 1 });
    });
    if (!choices.length) { this.setData({ fErr: '请至少选择一个志愿' }); return; }
    const that = this;
    this.setData({ saving: true, fErr: '' });
    request('/benchmark/topic-choices', {
      method: 'POST',
      data: { round_id: round.id, choices: choices }
    }).then(function (res) {
      that.setData({ saving: false });
      if (!(res.data && res.data.success)) {
        that.setData({ fErr: (res.data && res.data.message) || '提交失败' }); return;
      }
      that.setData({ showForm: false });
      wx.showToast({ title: '志愿已提交', icon: 'success' });
      that.load();
    }).catch(function (e) { that.setData({ saving: false, fErr: e.message }); });
  }
});
