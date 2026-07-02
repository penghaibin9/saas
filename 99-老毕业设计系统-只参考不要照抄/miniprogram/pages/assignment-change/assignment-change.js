const { get, request } = require('../../utils/request');

Page({
  data: {
    loading: true, list: [], type: 'transfer', assignmentId: null,
    enterprises: [], entIndex: 0, reason: ''
  },

  onLoad(q) {
    this.setData({
      type: q.type || 'transfer',
      assignmentId: q.assignment_id ? Number(q.assignment_id) : null
    });
    this.load();
  },

  load() {
    const that = this;
    this.setData({ loading: true });
    Promise.all([
      get('/assignment-changes?page_size=20'),
      this.data.type === 'transfer' ? get('/enterprises?page_size=100') : Promise.resolve({ list: [] })
    ]).then(function (arr) {
      const ents = ((arr[1] && arr[1].list) || []).map(e => ({ id: e.id, name: e.name }));
      that.setData({
        loading: false,
        list: (arr[0] && arr[0].list) || [],
        enterprises: ents,
        entIndex: 0
      });
    }).catch(function () {
      that.setData({ loading: false });
    });
  },

  onReason(e) { this.setData({ reason: e.detail.value }); },

  onEntPick(e) { this.setData({ entIndex: Number(e.detail.value) }); },

  submit() {
    const { type, assignmentId, reason, enterprises, entIndex } = this.data;
    if (!assignmentId) { wx.showToast({ title: '请从我的实习进入', icon: 'none' }); return; }
    if (!reason.trim()) { wx.showToast({ title: '请填写原因', icon: 'none' }); return; }
    const body = { assignment_id: assignmentId, change_type: type, reason: reason.trim() };
    if (type === 'transfer') {
      const ent = enterprises[entIndex];
      if (!ent) { wx.showToast({ title: '请选择新单位', icon: 'none' }); return; }
      body.new_enterprise_id = ent.id;
    }
    request('/assignment-changes', { method: 'POST', data: body }).then(function () {
      wx.showToast({ title: '已提交' });
      wx.navigateBack();
    }).catch(function (e) {
      wx.showToast({ title: e.message || '提交失败', icon: 'none' });
    });
  }
});
