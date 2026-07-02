const { get, request } = require('../../utils/request');
const { fmtDate } = require('../../utils/util');

const TABS = [
  { k: 'all', label: '全部' },
  { k: 'apps', label: '申请' },
  { k: 'logs', label: '周报' },
  { k: 'leaves', label: '请假' },
  { k: 'achs', label: '成果' },
  { k: 'reports', label: '报告' },
  { k: 'asg', label: '换岗' },
  { k: 'agr', label: '协议' }
];

Page({
  data: {
    loading: true,
    err: '',
    activeTab: 'all',
    tabs: TABS,
    apps: [], logs: [], leaves: [], achs: [], reports: [], asgChanges: [], pendingAgreements: [],
    showLog: false, logDetail: null,
    showGrade: false, gradeId: null, gradeName: '', gScore: '', gCmt: '', gErr: '', gSaving: false
  },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(2); }
    const section = wx.getStorageSync('review_section');
    if (section) {
      wx.removeStorageSync('review_section');
      this.setData({ activeTab: section });
    }
    this.load();
  },
  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([
      get('/applications?status=0&page_size=30'),
      get('/intern-logs?status=1&page_size=30'),
      get('/leaves?status=1&page_size=30'),
      get('/gd-achievements?status=0&page_size=30'),
      get('/reports?status=1&page_size=30'),
      get('/assignment-changes?status=0&page_size=30'),
      get('/agreements?page_size=50')
    ]).then(function (arr) {
      const leaves = ((arr[2] && arr[2].list) || []).map(function (l) {
        return Object.assign({}, l, { startText: fmtDate(l.start_date), endText: fmtDate(l.end_date) });
      });
      const agreements = (arr[6] && arr[6].list) || [];
      const pendingAgreements = agreements.filter(function (a) {
        return a.student_signed && !a.teacher_signed && a.status !== 2 && a.status !== 3;
      });
      that.setData({
        loading: false,
        apps: (arr[0] && arr[0].list) || [],
        logs: (arr[1] && arr[1].list) || [],
        leaves: leaves,
        achs: (arr[3] && arr[3].list) || [],
        reports: (arr[4] && arr[4].list) || [],
        asgChanges: (arr[5] && arr[5].list) || [],
        pendingAgreements: pendingAgreements,
        tabs: TABS.map(function (t) {
          const counts = {
            all: ((arr[0] && arr[0].list) || []).length + ((arr[1] && arr[1].list) || []).length +
              leaves.length + ((arr[3] && arr[3].list) || []).length + ((arr[4] && arr[4].list) || []).length +
              ((arr[5] && arr[5].list) || []).length + pendingAgreements.length,
            apps: ((arr[0] && arr[0].list) || []).length,
            logs: ((arr[1] && arr[1].list) || []).length,
            leaves: leaves.length,
            achs: ((arr[3] && arr[3].list) || []).length,
            reports: ((arr[4] && arr[4].list) || []).length,
            asg: ((arr[5] && arr[5].list) || []).length,
            agr: pendingAgreements.length
          };
          return Object.assign({}, t, { count: counts[t.k] || 0 });
        })
      });
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  done(msg) { wx.showToast({ title: msg, icon: 'none' }); this.load(); },
  noop() {},

  // 快捷理由选择：先弹常用理由，选"自定义"再手动输入（对标商业产品快捷评语）
  pickReason(quick, cb) {
    const items = quick.concat(['✏️ 自定义输入…']);
    wx.showActionSheet({
      itemList: items,
      success(r) {
        if (r.tapIndex < quick.length) { cb(quick[r.tapIndex]); return; }
        wx.showModal({
          title: '请输入理由', editable: true, placeholderText: '请输入具体理由',
          success(m) { if (m.confirm) cb((m.content || '').trim() || '不符合要求'); }
        });
      }
    });
  },

  switchTab(e) {
    this.setData({ activeTab: e.currentTarget.dataset.k });
  },

  // 申请
  reviewApp(e) {
    const id = e.currentTarget.dataset.id;
    const agree = e.currentTarget.dataset.agree;
    const that = this;
    if (agree) {
      request('/applications/' + id + '/teacher-review', { method: 'PUT', data: { agree: true, opinion: '同意' } })
        .then(function () { that.done('已处理'); });
    } else {
      this.pickReason(['岗位与专业不对口', '企业资质材料不全', '实习协议未完善', '需先与家长/学校确认'], function (reason) {
        request('/applications/' + id + '/teacher-review', { method: 'PUT', data: { agree: false, opinion: reason } })
          .then(function () { that.done('已处理'); });
      });
    }
  },

  // 周报
  viewLog(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    get('/intern-logs/' + id).then(function (l) {
      if (l) that.setData({ showLog: true, logDetail: l });
    });
  },
  closeLog() { this.setData({ showLog: false, logDetail: null }); },

  reviewLog(e) {
    const id = e.currentTarget.dataset.id;
    const agree = e.currentTarget.dataset.agree;
    const that = this;
    this.setData({ showLog: false });
    if (agree) {
      request('/intern-logs/' + id + '/review', { method: 'PUT', data: { agree: true } })
        .then(function () { that.done('已处理'); });
    } else {
      this.pickReason(['内容过于简单，请补充工作细节', '与实习岗位内容无关', '格式不规范，请按模板撰写', '缺少本周收获与问题总结'], function (reason) {
        request('/intern-logs/' + id + '/review', { method: 'PUT', data: { agree: false, reject_reason: reason } })
          .then(function () { that.done('已处理'); });
      });
    }
  },

  // 周报一键全部通过
  batchPassLogs() {
    const logs = this.data.logs;
    if (!logs.length) return;
    const that = this;
    wx.showModal({
      title: '一键通过',
      content: '将通过当前 ' + logs.length + ' 篇待批周报/月报，确定？',
      success(r) {
        if (!r.confirm) return;
        wx.showLoading({ title: '批量处理中…' });
        Promise.all(logs.map(function (l) {
          return request('/intern-logs/' + l.id + '/review', { method: 'PUT', data: { agree: true } }).catch(function () {});
        })).then(function () {
          wx.hideLoading();
          that.done('已全部通过');
        });
      }
    });
  },

  // 请假
  reviewLeave(e) {
    const id = e.currentTarget.dataset.id;
    const agree = e.currentTarget.dataset.agree;
    const that = this;
    if (agree) {
      request('/leaves/' + id + '/review', { method: 'PUT', data: { agree: true } })
        .then(function () { that.done('已处理'); });
    } else {
      this.pickReason(['请假事由不充分', '请假时间过长，请分段申请', '需补充证明材料', '与企业考勤安排冲突'], function (reason) {
        request('/leaves/' + id + '/review', { method: 'PUT', data: { agree: false, reject_reason: reason } })
          .then(function () { that.done('已处理'); });
      });
    }
  },

  // 成果
  reviewAch(e) {
    const id = e.currentTarget.dataset.id;
    const pass = e.currentTarget.dataset.pass;
    const that = this;
    if (pass) {
      request('/gd-achievements/' + id + '/review', { method: 'PUT', data: { status: 1 } })
        .then(function () { that.done('已处理'); });
    } else {
      this.pickReason(['材料不完整，请补充', '内容质量不达标，需修改', '格式不符合要求', '与选题方向不符'], function (reason) {
        request('/gd-achievements/' + id + '/review', { method: 'PUT', data: { status: 2, reject_reason: reason } })
          .then(function () { that.done('已处理'); });
      });
    }
  },

  // 报告评分
  openGrade(e) {
    const r = e.currentTarget.dataset.item;
    this.setData({ showGrade: true, gradeId: r.id, gradeName: r.student_name || '', gScore: '', gCmt: '', gErr: '' });
  },
  closeGrade() { this.setData({ showGrade: false }); },
  onScore(e) { this.setData({ gScore: e.detail.value }); },
  onCmt(e) { this.setData({ gCmt: e.detail.value }); },
  onQuickScore(e) { this.setData({ gScore: String(e.currentTarget.dataset.v) }); },
  onQuickCmt(e) {
    const t = e.currentTarget.dataset.t;
    const cur = (this.data.gCmt || '').trim();
    this.setData({ gCmt: cur ? (cur + '；' + t) : t });
  },
  submitGrade() {
    const sc = Number(this.data.gScore);
    if (!(sc >= 0 && sc <= 100)) { this.setData({ gErr: '请输入 0-100 的成绩' }); return; }
    this.setData({ gSaving: true, gErr: '' });
    const that = this;
    request('/reports/' + this.data.gradeId + '/review', { method: 'PUT', data: { teacher_score: sc, teacher_comment: (this.data.gCmt || '').trim() } })
      .then(function (res) {
        that.setData({ gSaving: false });
        if (!(res.data && res.data.success)) { that.setData({ gErr: res.data.message || '评阅失败' }); return; }
        that.setData({ showGrade: false });
        that.done('已评阅');
      })
      .catch(function (e) { that.setData({ gSaving: false, gErr: e.message }); });
  },

  reviewAsg(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    wx.showModal({
      title: '换岗/终止审批', content: '通过教师审批？', confirmText: '通过', cancelText: '驳回',
      success(r) {
        const approve = !!r.confirm;
        wx.showModal({
          title: '审批意见', editable: true, placeholderText: '可选',
          success(r2) {
            if (!r2.confirm && !approve) return;
            request('/assignment-changes/' + id + '/teacher-review', {
              method: 'PUT', data: { approve: approve, opinion: (r2.content || '').trim() }
            }).then(function () { that.done('已处理'); });
          }
        });
      }
    });
  },

  teacherSignAgreement(e) {
    const id = e.currentTarget.dataset.id;
    const that = this;
    wx.showModal({
      title: '教师会签', content: '确认会签该协议？',
      success(r) {
        if (!r.confirm) return;
        request('/agreements/' + id + '/teacher-sign', { method: 'PUT', data: {} })
          .then(function () { that.done('会签成功'); });
      }
    });
  }
});
