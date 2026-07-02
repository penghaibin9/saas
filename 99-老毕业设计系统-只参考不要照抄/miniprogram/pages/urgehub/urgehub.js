const { get, request } = require('../../utils/request');

Page({
  data: {
    loading: true, err: '',
    noCheckin: [], noWeekly: [], noConsent: [], noAppraisal: [],
    urging: false
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    get('/benchmark/urge-list').then(function (d) {
      that.setData({
        loading: false,
        noCheckin: d.noCheckin || [],
        noWeekly: d.noWeekly || [],
        noConsent: d.noConsent || [],
        noAppraisal: d.noAppraisal || []
      });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  urge(e) {
    const kind = e.currentTarget.dataset.kind;
    const map = {
      noCheckin: { list: this.data.noCheckin, title: '打卡催办', content: '请及时完成今日实习打卡' },
      noWeekly: { list: this.data.noWeekly, title: '周报催办', content: '请及时提交实习周报' },
      noConsent: { list: this.data.noConsent, title: '家长知情催办', content: '请尽快上传家长知情同意书' },
      noAppraisal: { list: this.data.noAppraisal, title: '鉴定表催办', content: '请尽快提交实习鉴定表' }
    };
    const cfg = map[kind];
    if (!cfg || !cfg.list.length) {
      wx.showToast({ title: '暂无待催办学生', icon: 'none' }); return;
    }
    const ids = cfg.list.slice(0, 30).map(function (x) { return x.student_id; }).filter(Boolean);
    const that = this;
    wx.showModal({
      title: '发送催办',
      content: '将向 ' + ids.length + ' 名学生发送站内提醒，是否继续？',
      success(r) {
        if (!r.confirm) return;
        that.setData({ urging: true });
        request('/benchmark/urge-notify', {
          method: 'POST',
          data: { student_ids: ids, title: cfg.title, content: cfg.content }
        }).then(function (res) {
          that.setData({ urging: false });
          wx.showToast({
            title: res.data && res.data.success ? ('已发送 ' + (res.data.data && res.data.data.count || ids.length) + ' 人') : (res.data.message || '失败'),
            icon: 'none'
          });
        }).catch(function (err) {
          that.setData({ urging: false });
          wx.showToast({ title: err.message, icon: 'none' });
        });
      }
    });
  }
});
