const { get } = require('../../utils/request');

Page({
  data: { loading: true, err: '', grade: null },

  onShow() { this.load(); },

  load() {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/gd-grades/mine').then(function (g) {
      that.setData({ loading: false, grade: g || null });
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
    });
  }
});
