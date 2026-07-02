const { get, request } = require('../../utils/request');

const PAGE_SIZE = 30;

// 列表行装饰：彩色头像 + 风险标记（对标商业产品的学生预警）
function decorate(r) {
  const name = r.student_name || '';
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 997;
  const tags = [];
  if (!r.enterprise_name) tags.push({ t: '未分配', c: 'tag-m' });
  if (!Number(r.checkin_count)) tags.push({ t: '无打卡', c: 'tag-r' });
  if (!Number(r.weekly_count)) tags.push({ t: '零周报', c: 'tag-y' });
  return Object.assign({}, r, {
    avIdx: h % 6,
    avTxt: name.length > 2 ? name.slice(-2) : (name || '?'),
    riskTags: tags
  });
}

Page({
  data: {
    loading: true,
    loadingMore: false,
    err: '',
    keyword: '',
    total: 0,
    list: [],
    page: 1,
    hasMore: false,
    searching: false,
    filter: 'all',
    filters: [
      { k: 'all', label: '全部' },
      { k: 'nocheckin', label: '无打卡' },
      { k: 'nolog', label: '零周报' },
      { k: 'noasg', label: '未分配' }
    ],
    shown: []
  },

  setFilter(e) {
    this.setData({ filter: e.currentTarget.dataset.k });
    this.applyFilter();
  },

  applyFilter() {
    const f = this.data.filter;
    const list = this.data.list;
    let shown = list;
    if (f === 'nocheckin') shown = list.filter(function (r) { return !Number(r.checkin_count); });
    else if (f === 'nolog') shown = list.filter(function (r) { return !Number(r.weekly_count); });
    else if (f === 'noasg') shown = list.filter(function (r) { return !r.enterprise_name; });
    this.setData({ shown: shown });
  },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(1); }
    this.load(true);
  },

  onPullDownRefresh() {
    this.load(true, function () { wx.stopPullDownRefresh(); });
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading && !this.data.loadingMore) {
      this.loadMore();
    }
  },

  onSearchInput(e) {
    const kw = (e.detail.value || '').trim();
    this._pendingKw = kw;
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => {
      if (this._pendingKw === kw) {
        this.setData({ keyword: kw, searching: !!kw });
        this.load(true);
      }
    }, 350);
  },

  onSearchConfirm(e) {
    clearTimeout(this._searchTimer);
    const kw = ((e.detail && e.detail.value) || this.data.keyword || '').trim();
    this.setData({ keyword: kw, searching: !!kw });
    this.load(true);
  },

  onClearSearch() {
    clearTimeout(this._searchTimer);
    this.setData({ keyword: '', searching: false });
    this.load(true);
  },

  reload() {
    this.load(true);
  },

  load(reset, done) {
    const that = this;
    const page = reset ? 1 : this.data.page;
    if (reset) {
      this.setData({ loading: true, err: '', page: 1, list: [], hasMore: false });
    }
    get('/intern-stats/process', {
      data: {
        page: page,
        page_size: PAGE_SIZE,
        keyword: this.data.keyword || undefined
      }
    }).then(function (d) {
      const rows = ((d && d.list) || []).map(decorate);
      const total = (d && d.total) || 0;
      that.setData({
        loading: false,
        searching: false,
        total: total,
        list: reset ? rows : that.data.list.concat(rows),
        page: page,
        hasMore: page * PAGE_SIZE < total
      });
      that.applyFilter();
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, searching: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  loadMore() {
    const that = this;
    const nextPage = this.data.page + 1;
    this.setData({ loadingMore: true });
    get('/intern-stats/process', {
      data: {
        page: nextPage,
        page_size: PAGE_SIZE,
        keyword: this.data.keyword || undefined
      }
    }).then(function (d) {
      const rows = ((d && d.list) || []).map(decorate);
      const total = (d && d.total) || that.data.total;
      that.setData({
        loadingMore: false,
        total: total,
        list: that.data.list.concat(rows),
        page: nextPage,
        hasMore: nextPage * PAGE_SIZE < total
      });
      that.applyFilter();
    }).catch(function (e) {
      that.setData({ loadingMore: false });
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    });
  },

  tapStudent(e) {
    const ds = e.currentTarget.dataset;
    const name = ds.name || '该生';
    const id = ds.id;
    if (!id) return;
    const that = this;
    wx.showActionSheet({
      itemList: ['重置密码为 123456'],
      success(r) {
        if (r.tapIndex === 0) that.resetPwd(id, name);
      }
    });
  },

  resetPwd(studentId, studentName) {
    wx.showModal({
      title: '重置密码',
      content: '确定将「' + studentName + '」的密码重置为 123456？该生下次登录需改密。',
      success(r) {
        if (!r.confirm) return;
        request('/teacher/students/' + studentId + '/reset-password', { method: 'PUT', data: {} })
          .then(function (res) {
            wx.showToast({
              title: res.data && res.data.success ? '已重置' : (res.data.message || '失败'),
              icon: 'none'
            });
          })
          .catch(function (err) {
            wx.showToast({ title: err.message || '失败', icon: 'none' });
          });
      }
    });
  }
});
