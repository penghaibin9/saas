const { get, request } = require('../../utils/request');
const app = getApp();

const TYPES = [
  { value: 'employment', label: '就业' },
  { value: 'study', label: '升学' },
  { value: 'business', label: '创业' },
  { value: 'other', label: '其他' }
];

Page({
  data: {
    loading: true, err: '', types: TYPES, typeIdx: 0,
    company: '', position: '', city: '', salary: '', remark: '', saving: false, saved: false,
    isTeacher: false, stats: null
  },

  onShow() {
    const u = app.globalData.user || {};
    this.setData({ isTeacher: u.role && u.role !== 4 });
    this.load();
  },

  load() {
    const that = this;
    this.setData({ loading: true, err: '' });
    if (this.data.isTeacher) {
      get('/benchmark/employment/stats').then(function (s) {
        that.setData({ loading: false, stats: s || null });
      }).catch(function (e) { that.setData({ loading: false, err: e.message || '加载失败' }); });
      return;
    }
    get('/benchmark/employment').then(function (d) {
      if (!d) {
        that.setData({ loading: false, saved: false });
        return;
      }
      const idx = TYPES.findIndex(function (t) { return t.value === d.dest_type; });
      that.setData({
        loading: false, saved: true,
        typeIdx: idx >= 0 ? idx : 0,
        company: d.company_name || '',
        position: d.position_title || '',
        city: d.city || '',
        salary: d.salary_range || '',
        remark: d.remark || ''
      });
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
    });
  },

  onType(e) { this.setData({ typeIdx: Number(e.detail.value) }); },
  onCompany(e) { this.setData({ company: e.detail.value }); },
  onPosition(e) { this.setData({ position: e.detail.value }); },
  onCity(e) { this.setData({ city: e.detail.value }); },
  onSalary(e) { this.setData({ salary: e.detail.value }); },
  onRemark(e) { this.setData({ remark: e.detail.value }); },

  save() {
    const t = TYPES[this.data.typeIdx];
    if (!t) return;
    const that = this;
    this.setData({ saving: true });
    request('/benchmark/employment', {
      method: 'POST',
      data: {
        dest_type: t.value,
        company_name: this.data.company,
        position_title: this.data.position,
        city: this.data.city,
        salary_range: this.data.salary,
        remark: this.data.remark
      }
    }).then(function (res) {
      that.setData({ saving: false });
      wx.showToast({ title: res.data && res.data.success ? '已保存' : (res.data.message || '失败'), icon: 'none' });
      if (res.data && res.data.success) that.load();
    }).catch(function (e) { that.setData({ saving: false }); wx.showToast({ title: e.message, icon: 'none' }); });
  }
});
