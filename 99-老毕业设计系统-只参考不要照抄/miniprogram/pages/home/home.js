const app = getApp();
const { get } = require('../../utils/request');
const { buildFlowSteps, NAV } = require('../../utils/benchmarkFlow');

function pct(n, r) {
  n = Number(n) || 0; r = Number(r) || 0;
  return r > 0 ? Math.min(100, Math.round(n / r * 100)) : (n > 0 ? 100 : 0);
}

const STU_QUICK = [
  { icon: '📍', label: '打卡', url: '/pages/checkin/checkin', tab: '1', cls: 'qa-checkin' },
  { icon: '📝', label: '周报', url: '/pages/logs/logs', tab: '1', cls: 'qa-log' },
  { icon: '🏖️', label: '请假', url: '/pages/leave/leave', cls: 'qa-leave' },
  { icon: '📄', label: '报告', url: '/pages/reports/reports', cls: 'qa-report' }
];

const STU_GROUPS = [
  {
    title: '实习监管',
    desc: '全流程线上办理',
    items: [
      { icon: '👪', label: '家长知情', url: '/pages/parentconsent/parentconsent', cls: 'ic-b' },
      { icon: '📋', label: '实习鉴定', url: '/pages/appraisal/appraisal', cls: 'ic-g' },
      { icon: '📊', label: '实习考评', url: '/pages/internscore/internscore', cls: 'ic-t' },
      { icon: '📑', label: '实习协议', url: '/pages/agreement/agreement', cls: 'ic-r' },
      { icon: '🛡️', label: '实习保险', url: '/pages/insurances/insurances', cls: 'ic-g' },
      { icon: '💼', label: '就业去向', url: '/pages/employment/employment', cls: 'ic-p' },
      { icon: '📝', label: '免实习', url: '/pages/alternative/alternative', cls: 'ic-o' },
      { icon: '🆘', label: '投诉上报', url: '/pages/complaint/complaint', cls: 'ic-r' }
    ]
  },
  {
    title: '毕业设计',
    desc: '选题到答辩全周期',
    items: [
      { icon: '📋', label: '任务书', url: '/pages/taskbook/taskbook', cls: 'ic-b' },
      { icon: '🔄', label: '选题互选', url: '/pages/topicround/topicround', cls: 'ic-t' },
      { icon: '🎓', label: '我的成果', url: '/pages/achievements/achievements', cls: 'ic-p' },
      { icon: '🔍', label: '查重检测', url: '/pages/plagiarism/plagiarism', cls: 'ic-y' },
      { icon: '🎤', label: '我的答辩', url: '/pages/mydefense/mydefense', cls: 'ic-r' },
      { icon: '📌', label: '毕设选题', url: '/pages/topics/topics', cls: 'ic-r' },
      { icon: '🗓️', label: '任务节点', url: '/pages/tasks/tasks', cls: 'ic-t' },
      { icon: '🏅', label: '毕设成绩', url: '/pages/grade/grade', cls: 'ic-o' }
    ]
  },
  {
    title: '实习事务',
    items: [
      { icon: '🏢', label: '我的实习', url: '/pages/assignment/assignment', cls: 'ic-b' },
      { icon: '💼', label: '岗位申请', url: '/pages/positions/positions', cls: 'ic-p' },
      { icon: '📋', label: '实习申请', url: '/pages/applications/applications', cls: 'ic-b' },
      { icon: '📢', label: '公示公告', url: '/pages/announcements/announcements', cls: 'ic-b' },
      { icon: '🔔', label: '通知中心', url: '/pages/notifications/notifications', cls: 'ic-y', badgeKey: 'unread' },
      { icon: '👤', label: '个人资料', url: '/pages/profile/profile', cls: 'ic-m' }
    ]
  }
];

const TEA_QUICK = [
  { icon: '✅', label: '待批阅', url: '/pages/review/review', cls: 'qa-review', badgeKey: 'pending' },
  { icon: '📣', label: '催办', url: '/pages/urgehub/urgehub', cls: 'qa-urge' },
  { icon: '👨‍🎓', label: '实习生', url: '/pages/students/students', tab: '1', cls: 'qa-stu' },
  { icon: '⚠️', label: '风险', url: '/pages/risk/risk', cls: 'qa-risk', badgeKey: 'risk' }
];

const TEA_GROUPS = [
  {
    title: '实习监管',
    items: [
      { icon: '📋', label: '任务书', url: '/pages/taskbook/taskbook', cls: 'ic-b' },
      { icon: '🔄', label: '课题互选', url: '/pages/topicround/topicround', cls: 'ic-t' },
      { icon: '👪', label: '家长知情', url: '/pages/parentconsent/parentconsent', cls: 'ic-b', badgeKey: 'consent' },
      { icon: '📋', label: '鉴定审核', url: '/pages/appraisal/appraisal', cls: 'ic-g', badgeKey: 'appraisal' },
      { icon: '🚗', label: '教师巡访', url: '/pages/teachervisit/teachervisit', cls: 'ic-t' },
      { icon: '📊', label: '考评发布', url: '/pages/internscore/internscore', cls: 'ic-t' },
      { icon: '👩‍🏫', label: '班级工作台', url: '/pages/classteacher/classteacher', cls: 'ic-o' },
      { icon: '📑', label: '协议会签', url: '/pages/agreement/agreement', cls: 'ic-g' }
    ]
  },
  {
    title: '指导管理',
    items: [
      { icon: '📖', label: '指导记录', url: '/pages/guidance/guidance', cls: 'ic-p' },
      { icon: '🗂️', label: '工作记录', url: '/pages/trecords/trecords', cls: 'ic-o' },
      { icon: '🔎', label: '质量检查', url: '/pages/quality/quality', cls: 'ic-t' },
      { icon: '🎓', label: '答辩评分', url: '/pages/defense/defense', cls: 'ic-p' },
      { icon: '📢', label: '公示公告', url: '/pages/announcements/announcements', cls: 'ic-b' },
      { icon: '🔔', label: '通知中心', url: '/pages/notifications/notifications', cls: 'ic-y', badgeKey: 'unread' }
    ]
  }
];

function alertLevelCls(level) {
  if (level === 'error') return 'err';
  if (level === 'warning') return 'warn';
  return 'info';
}

function alertIcon(key) {
  const map = {
    checkins: '📍', parentconsent: '👪', appraisal: '📋', taskbook: '📋',
    topicround: '🔄', internscore: '📊', plagiarism: '🔍', agreements: '📑',
    reviewhub: '✅', asgchange: '🔄', insurancehub: '🛡️', 'gd-home': '🎓',
    'gd-achievements': '📄', quality: '🔎', riskcomplaint: '🆘'
  };
  return map[key] || '📌';
}

function alertSection(a) {
  if (!a || a.key !== 'reviewhub') return '';
  const t = a.title || '';
  if (t.indexOf('申请') >= 0) return 'apps';
  if (t.indexOf('周报') >= 0 || t.indexOf('月报') >= 0) return 'logs';
  if (t.indexOf('请假') >= 0) return 'leaves';
  if (t.indexOf('换岗') >= 0 || t.indexOf('终止') >= 0) return 'asg';
  if (t.indexOf('协议') >= 0) return 'agr';
  return '';
}

function enrichAlerts(list) {
  return (list || []).map(function (a) {
    return Object.assign({}, a, { icon: alertIcon(a.key), section: alertSection(a) });
  });
}

Page({
  data: {
    loading: true, err: '', isTeacher: false, user: {},
    progress: {}, assignment: null, pending: {}, assignedStudents: 0, unread: 0,
    progCheckin: 0, progWeekly: 0, progMonthly: 0,
    stuQuick: STU_QUICK, teaQuick: TEA_QUICK,
    menuGroups: [], totalPending: 0, riskBadge: 0,
    risk: {}, insuranceWarn: 0, flowAlerts: [], unsignedAgreements: 0, asgChangeActive: null,
    flowSteps: [], flowDone: 0, flowPct: 0, benchmarkPending: {},
    todoItems: [], metricCells: [], graduationYear: new Date().getFullYear()
  },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(0); }
    this.setData({ user: app.globalData.user || {}, isTeacher: app.isTeacher(), graduationYear: app.globalData.graduationYear });
    this.load();
    this.loadUnread();
  },

  onPullDownRefresh() { this.load(function () { wx.stopPullDownRefresh(); }); },

  loadUnread() {
    const that = this;
    get('/notifications/unread-count').then(function (d) {
      that.setData({ unread: (d && d.count) || 0 });
      that.applyBadges();
    }).catch(function () {});
  },

  applyBadges() {
    const u = this.data.unread;
    const tp = this.data.totalPending;
    const rb = this.data.riskBadge;
    const bm = this.data.benchmarkPending || {};

    if (!this.data.isTeacher) {
      const groups = STU_GROUPS.map(function (g) {
        return {
          title: g.title, desc: g.desc || '',
          items: g.items.map(function (t) {
            const o = Object.assign({}, t);
            if (t.badgeKey === 'unread' && u) o.badge = u > 99 ? '99+' : u;
            return o;
          })
        };
      });
      const quick = STU_QUICK.map(function (q) { return Object.assign({}, q); });
      this.setData({ menuGroups: groups, stuQuick: quick });
    } else {
      const groups = TEA_GROUPS.map(function (g) {
        return {
          title: g.title, desc: g.desc || '',
          items: g.items.map(function (t) {
            const o = Object.assign({}, t);
            if (t.badgeKey === 'unread' && u) o.badge = u > 99 ? '99+' : u;
            if (t.badgeKey === 'consent' && bm.parentConsentPending) o.badge = bm.parentConsentPending;
            if (t.badgeKey === 'appraisal' && bm.appraisalPending) o.badge = bm.appraisalPending;
            return o;
          })
        };
      });
      const quick = TEA_QUICK.map(function (q) {
        const o = Object.assign({}, q);
        if (q.badgeKey === 'pending' && tp) o.badge = tp > 99 ? '99+' : tp;
        if (q.badgeKey === 'risk' && rb) o.badge = rb;
        return o;
      });
      this.setData({ menuGroups: groups, teaQuick: quick });
    }
  },

  buildTodos() {
    const items = [];
    const that = this;
    (this.data.flowAlerts || []).forEach(function (a) {
      items.push({
        key: a.key, title: a.title, desc: a.desc,
        cls: alertLevelCls(a.level), icon: a.icon || alertIcon(a.key), section: a.section || ''
      });
    });
    if (this.data.unsignedAgreements) {
      items.push({ key: 'agreements', title: '待签署协议', desc: this.data.unsignedAgreements + ' 份待处理', cls: 'warn', icon: '📑' });
    }
    if (this.data.asgChangeActive) {
      items.push({ key: 'asgchange', title: '换岗/终止进行中', desc: '点击查看进度', cls: 'info', icon: '🔄' });
    }
    if (this.data.insuranceWarn) {
      items.push({ key: 'insurancehub', title: '保险即将到期', desc: this.data.insuranceWarn + ' 份需关注', cls: 'warn', icon: '🛡️' });
    }
    if (!this.data.progress.checkedToday && this.data.assignment) {
      items.unshift({ key: 'checkins', title: '今日尚未打卡', desc: this.data.assignment.enterprise_name || '', cls: 'warn', icon: '📍' });
    }
    this.setData({ todoItems: items.slice(0, 5) });
  },

  buildMetrics(p) {
    const cells = [
      { v: p.applications || 0, l: '待审申请', icon: '📋', hot: (p.applications || 0) > 0, section: 'apps', url: '/pages/review/review' },
      { v: p.internLogs || 0, l: '待批周报', icon: '📝', hot: (p.internLogs || 0) > 0, section: 'logs', url: '/pages/review/review' },
      { v: p.leaves || 0, l: '待批请假', icon: '🏖️', hot: (p.leaves || 0) > 0, section: 'leaves', url: '/pages/review/review' },
      { v: p.achievements || 0, l: '待审成果', icon: '🎓', hot: (p.achievements || 0) > 0, section: 'achs', url: '/pages/review/review' },
      { v: p.reports || 0, l: '待评报告', icon: '📄', hot: (p.reports || 0) > 0, section: 'reports', url: '/pages/review/review' },
      { v: p.qualityChecks || 0, l: '待质检', icon: '🔎', hot: (p.qualityChecks || 0) > 0, url: '/pages/quality/quality' },
      { v: p.asgChanges || 0, l: '换岗/终止', icon: '🔄', hot: (p.asgChanges || 0) > 0, section: 'asg', url: '/pages/review/review' },
      { v: p.complaints || 0, l: '本组投诉', icon: '🆘', hot: (p.complaints || 0) > 0, url: '/pages/risk/risk' }
    ].map(function (c) {
      c.zero = c.v === 0;
      c.goText = c.v > 0 ? '去处理 ›' : '查看';
      return c;
    });
    this.setData({ metricCells: cells });
  },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    const reqs = [get('/workbench')];
    if (app.isTeacher()) reqs.push(get('/risk/warnings').catch(function () { return null; }));
    else reqs.push(get('/insurances?page_size=20').catch(function () { return null; }));

    Promise.all(reqs).then(function (arr) {
      const d = arr[0] || {};
      if (app.isTeacher()) {
        const rk = (arr[1] && arr[1].summary) || {};
        const p = d.pending || {};
        const bm = d.benchmark || {};
        const totalPending = p.total != null ? p.total : (
          (p.applications || 0) + (p.internLogs || 0) + (p.leaves || 0) + (p.achievements || 0) +
          (p.reports || 0) + (p.qualityChecks || 0) + (p.asgChanges || 0) + (p.agreements || 0) + (p.complaints || 0)
        );
        that.setData({
          loading: false, pending: p, assignedStudents: d.assignedStudents || 0,
          totalPending: totalPending, risk: rk, riskBadge: (rk.high || 0) + (rk.medium || 0),
          flowAlerts: enrichAlerts(d.alerts), benchmarkPending: bm
        });
        that.buildMetrics(p);
        const tb = that.getTabBar();
        if (tb) tb.setBadge(totalPending);
      } else {
        const pr = d.progress || {};
        const ins = arr[1];
        const ilist = (ins && ins.list) || [];
        const now = Date.now();
        const pd = d.pending || {};
        const bm = d.benchmark || {};
        const steps = buildFlowSteps(bm);
        const doneN = steps.filter(function (s) { return s.done; }).length;
        const insuranceWarn = pd.insuranceWarn || ilist.filter(function (i) {
          if (!i.end_date) return false;
          return new Date(i.end_date).getTime() - now < 30 * 86400000;
        }).length;
        that.setData({
          loading: false, progress: pr, assignment: d.assignment || null,
          progCheckin: pct(pr.checkinCount, pr.reqCheckin),
          progWeekly: pct(pr.weeklyCount, pr.reqWeekly),
          progMonthly: pct(pr.monthlyCount, pr.reqMonthly),
          insuranceWarn: insuranceWarn,
          flowAlerts: enrichAlerts(d.alerts),
          unsignedAgreements: pd.unsignedAgreements || 0,
          asgChangeActive: d.asgChangeActive || null,
          flowSteps: steps,
          flowDone: doneN,
          flowPct: steps.length ? Math.round(doneN / steps.length * 100) : 0
        });
        that.buildTodos();
      }
      that.applyBadges();
      if (done) done();
    }).catch(function (e) {
      that.setData({ loading: false, err: e.message || '加载失败' });
      if (done) done();
    });
  },

  toNotifications() { wx.navigateTo({ url: '/pages/notifications/notifications' }); },
  goNav(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.navigateTo({ url: url });
  },
  goAlert(e) {
    const key = e.currentTarget.dataset.key;
    const section = e.currentTarget.dataset.section;
    if (section) wx.setStorageSync('review_section', section);
    const url = NAV[key] || e.currentTarget.dataset.url;
    if (!url) return;
    const tabs = ['/pages/checkin/checkin', '/pages/logs/logs', '/pages/students/students'];
    if (tabs.indexOf(url) >= 0) wx.switchTab({ url: url });
    else wx.navigateTo({ url: url });
  },
  goFlowStep(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.navigateTo({ url: url });
  },
  go(e) {
    const url = e.currentTarget.dataset.url;
    const tab = e.currentTarget.dataset.tab;
    if (tab) wx.switchTab({ url: url });
    else wx.navigateTo({ url: url });
  },

  goMetric(e) {
    const ds = e.currentTarget.dataset;
    const url = ds.url;
    if (!url) return;
    if (ds.section) wx.setStorageSync('review_section', ds.section);
    const isTab = ds.istab === 1 || ds.istab === '1';
    const v = Number(ds.v) || 0;
    if (v === 0 && isTab) {
      wx.showToast({ title: '暂无' + (ds.l || '待办'), icon: 'none', duration: 1200 });
    }
    if (isTab) wx.switchTab({ url: url });
    else wx.navigateTo({ url: url });
  },

  goProg(e) {
    const kind = e.currentTarget.dataset.kind;
    if (kind === 'checkin') wx.switchTab({ url: '/pages/checkin/checkin' });
    else wx.switchTab({ url: '/pages/logs/logs' });
  },

  goFlowDetail() {
    const steps = this.data.flowSteps || [];
    const next = steps.find(function (s) { return s.pending; }) || steps.find(function (s) { return !s.done; });
    if (next && next.url) wx.navigateTo({ url: next.url });
    else if (steps[0]) wx.navigateTo({ url: steps[0].url });
  }
});
