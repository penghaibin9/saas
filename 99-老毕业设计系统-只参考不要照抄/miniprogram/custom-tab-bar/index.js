const studentTabs = [
  { pagePath: '/pages/home/home', text: '首页', icon: '🏠' },
  { pagePath: '/pages/checkin/checkin', text: '打卡', icon: '📍' },
  { pagePath: '/pages/logs/logs', text: '周报', icon: '📝' },
  { pagePath: '/pages/mine/mine', text: '我的', icon: '👤' }
];
const teacherTabs = [
  { pagePath: '/pages/home/home', text: '首页', icon: '🏠' },
  { pagePath: '/pages/students/students', text: '实习生', icon: '🎓' },
  { pagePath: '/pages/mine/mine', text: '我的', icon: '👤' }
];

Component({
  data: {
    selected: 0,
    list: studentTabs,
    badge: 0
  },
  lifetimes: {
    attached() {
      this.refresh();
    }
  },
  pageLifetimes: {
    show() {
      this.refresh();
      const pages = getCurrentPages();
      const currentRoute = pages.length ? '/' + pages[pages.length - 1].route : '/pages/home/home';
      const selectedIndex = this.data.list.findIndex(function (item) { return item.pagePath === currentRoute; });
      if (selectedIndex >= 0) this.setData({ selected: selectedIndex });
    }
  },
  methods: {
    refresh() {
      const u = wx.getStorageSync('user');
      const list = (u && u.role === 3) ? teacherTabs : studentTabs;
      this.setData({ list });
    },
    setSelected(idx) {
      this.setData({ selected: idx });
    },
    setBadge(n) {
      this.setData({ badge: n || 0 });
    },
    onTap(e) {
      const path = e.currentTarget.dataset.path;
      const idx = e.currentTarget.dataset.index;
      this.setData({ selected: idx });
      wx.switchTab({ url: path });
    }
  }
});
