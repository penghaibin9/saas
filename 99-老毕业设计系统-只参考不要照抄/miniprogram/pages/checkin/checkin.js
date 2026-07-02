const { get, request, uploadFile, downloadFile } = require('../../utils/request');
const { fmtTime, haversine, toDate, pad } = require('../../utils/util');

Page({
  data: {
    loading: true,
    err: '',
    mine: {},
    hasGeo: false,
    records: [],
    // 地图
    mapLat: 0,
    mapLng: 0,
    markers: [],
    circles: [],
    distText: '',
    distOk: true,
    punching: false,
    photoPath: '',
    demoMode: false,
    currentSlot: 'day',
    clockTime: '',
    clockDate: '',
    weekNames: ['日', '一', '二', '三', '四', '五', '六'],
    calTitle: '',
    calCells: [],
    monthCount: 0,
    streak: 0
  },

  onShow() {
    const tb = this.getTabBar();
    if (tb) { tb.refresh(); tb.setSelected(1); }
    this.setData({ demoMode: !!getApp().globalData.demoMode });
    this.startClock();
    this.load();
  },

  onHide() { this.stopClock(); },
  onUnload() { this.stopClock(); },

  startClock() {
    const that = this;
    const WK = ['日', '一', '二', '三', '四', '五', '六'];
    const tick = function () {
      const n = new Date();
      that.setData({
        clockTime: pad(n.getHours()) + ':' + pad(n.getMinutes()) + ':' + pad(n.getSeconds()),
        clockDate: (n.getMonth() + 1) + '月' + n.getDate() + '日 星期' + WK[n.getDay()]
      });
    };
    tick();
    this.stopClock();
    this._clockTimer = setInterval(tick, 1000);
  },

  stopClock() {
    if (this._clockTimer) { clearInterval(this._clockTimer); this._clockTimer = null; }
  },

  // 根据打卡记录生成本月日历与连续打卡统计
  buildCalendar(rawList) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth(), today = now.getDate();
    const key = function (d) { return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); };
    const hit = {};
    (rawList || []).forEach(function (c) {
      const d = toDate(c.checkin_time);
      if (d) hit[key(d)] = 1;
    });
    // 连续打卡：自今天（或昨天）向前累计
    let streak = 0;
    const cur = new Date(y, m, today);
    if (!hit[key(cur)]) cur.setDate(cur.getDate() - 1);
    while (hit[key(cur)]) { streak++; cur.setDate(cur.getDate() - 1); }
    // 本月格子
    const lead = new Date(y, m, 1).getDay();
    const days = new Date(y, m + 1, 0).getDate();
    const cells = [];
    let monthCount = 0;
    for (let i = 0; i < lead; i++) cells.push({ t: '', cls: 'dim' });
    for (let d = 1; d <= days; d++) {
      const dt = new Date(y, m, d);
      let cls = '';
      if (hit[key(dt)]) { cls = 'hit'; monthCount++; }
      else if (d < today && dt.getDay() > 0 && dt.getDay() < 6) cls = 'miss';
      else if (d > today) cls = 'dim';
      if (d === today) cls += ' today';
      cells.push({ t: d, cls: cls });
    }
    this.setData({
      calTitle: y + '年' + (m + 1) + '月',
      calCells: cells,
      monthCount: monthCount,
      streak: streak
    });
  },

  onPullDownRefresh() {
    this.load(function () { wx.stopPullDownRefresh(); });
  },

  load(done) {
    const that = this;
    this.setData({ loading: true, err: '' });
    Promise.all([get('/checkins/mine'), get('/checkins?page_size=120')])
      .then(function (arr) {
        const mine = arr[0] || {};
        const recs = (arr[1] && arr[1].list) || [];
        that.buildCalendar(recs);
        const records = recs.slice(0, 10).map(function (c) {
          return {
            id: c.id,
            enterprise_name: c.enterprise_name || '打卡',
            timeText: fmtTime(c.checkin_time),
            address: c.address || '',
            within_range: c.within_range,
            distance: c.distance,
            photo: '',
            photoPath: c.photo_url || ''
          };
        });
        const hasGeo = mine.enterpriseLat != null && mine.enterpriseLng != null;
        const data = { loading: false, mine: mine, records: records, hasGeo: hasGeo };
        if (hasGeo) {
          const lat = Number(mine.enterpriseLat), lng = Number(mine.enterpriseLng);
          const radius = Number(mine.checkinRadius) || 0;
          data.mapLat = lat;
          data.mapLng = lng;
          data.markers = [{ id: 1, latitude: lat, longitude: lng, width: 32, height: 32, callout: { content: mine.enterprise || '实习单位', display: 'ALWAYS', padding: 6, borderRadius: 6 } }];
          data.circles = radius > 0 ? [{ latitude: lat, longitude: lng, radius: radius, color: '#0EA5E988', fillColor: '#0EA5E920', strokeWidth: 1 }] : [];
        }
        that.setData(data);
        // 受保护的打卡照片必须携带令牌下载，不能再使用匿名静态 URL 作为 image src。
        Promise.all(records.map(function (record) {
          if (!record.photoPath) return Promise.resolve(record);
          return downloadFile(record.photoPath).then(function (res) {
            return Object.assign({}, record, { photo: res.tempFilePath });
          }).catch(function () { return record; });
        })).then(function (securedRecords) {
          that.setData({ records: securedRecords });
        });
        if (done) done();
      })
      .catch(function (e) {
        that.setData({ loading: false, err: e.message || '加载失败' });
        if (done) done();
      });
  },

  gpsCheckin(e) {
    const that = this;
    const m = this.data.mine;
    // 双时段：根据按钮 data-slot 决定打 am(上班)/pm(下班)；单时段固定 day
    let slot = 'day';
    if (m.doubleSlot) {
      slot = (e && e.currentTarget && e.currentTarget.dataset.slot) || (m.checkedAm ? 'pm' : 'am');
      if ((slot === 'am' && m.checkedAm) || (slot === 'pm' && m.checkedPm)) {
        wx.showToast({ title: slot === 'am' ? '上班已打卡' : '下班已打卡', icon: 'none' });
        return;
      }
    } else if (m.checkedToday) {
      return;
    }
    if (this.data.punching) return;
    this.setData({ currentSlot: slot, punching: true });
    wx.getLocation({
      type: 'gcj02',
      success(res) {
        that.afterLocate(res.latitude, res.longitude);
      },
      fail() {
        that.setData({ punching: false });
        if (that.data.mine.enterpriseLat != null) {
          wx.showModal({
            title: '定位失败',
            content: '无法获取位置，是否使用"模拟在岗位置"打卡（演示）？',
            success(r) { if (r.confirm) that.simCheckin(); }
          });
        } else {
          wx.showToast({ title: '定位失败', icon: 'none' });
        }
      }
    });
  },

  simCheckin() {
    const m = this.data.mine;
    if (m.enterpriseLat == null) { wx.showToast({ title: '企业未设坐标', icon: 'none' }); return; }
    if (m.doubleSlot && !this.data.currentSlot) {
      this.setData({ currentSlot: m.checkedAm ? 'pm' : 'am' });
    }
    this.setData({ punching: true });
    this.afterLocate(Number(m.enterpriseLat), Number(m.enterpriseLng));
  },

  // 现场拍照（仅相机来源，防代打卡）
  choosePhoto() {
    const that = this;
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: ['camera'], sizeType: ['compressed'], camera: 'back',
      success(res) {
        const f = res.tempFiles && res.tempFiles[0];
        if (!f) return;
        wx.compressImage({
          src: f.tempFilePath, quality: 70,
          success(c) { that.setData({ photoPath: c.tempFilePath || f.tempFilePath }); },
          fail() { that.setData({ photoPath: f.tempFilePath }); }
        });
      },
      fail() {}
    });
  },

  previewPhoto(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.previewImage({ urls: [url] });
  },

  afterLocate(lat, lng) {
    const that = this;
    const m = this.data.mine;
    // 展示距离
    if (m.enterpriseLat != null) {
      const d = haversine(lat, lng, Number(m.enterpriseLat), Number(m.enterpriseLng));
      const radius = Number(m.checkinRadius) || 0;
      const ok = radius === 0 || d <= radius;
      this.setData({
        distText: '距实习单位 ' + d + ' 米 · ' + (ok ? '在范围内 ✓' : '超出范围 ✗'),
        distOk: ok,
        markers: this.data.markers.concat([{ id: 2, latitude: lat, longitude: lng, width: 28, height: 28, callout: { content: '我的位置', display: 'ALWAYS', padding: 6, borderRadius: 6 } }])
      });
      if (radius > 0 && !ok) {
        this.setData({ punching: false });
        wx.showModal({
          title: '不在打卡范围',
          content: '您当前距实习单位 ' + d + ' 米，超出允许范围（' + radius + ' 米）。请靠近实习单位后再打卡。',
          showCancel: false
        });
        return;
      }
    }
    this.doSubmitCheckin(lat, lng);
  },

  doSubmitCheckin(lat, lng) {
    const that = this;
    const onOk = function (data) {
      that.setData({ punching: false });
      if (data && data.success) {
        that.setData({ photoPath: '' });
        wx.showToast({ title: '打卡成功', icon: 'success' });
        setTimeout(function () { that.load(); }, 700);
      } else {
        wx.showToast({ title: (data && data.message) || '打卡失败', icon: 'none' });
      }
    };
    const onErr = function (e) {
      that.setData({ punching: false });
      wx.showToast({ title: e.message || '打卡失败', icon: 'none' });
    };

    const slot = this.data.currentSlot || 'day';
    if (this.data.photoPath) {
      uploadFile('/checkins', this.data.photoPath, { latitude: String(lat), longitude: String(lng), address: '小程序拍照打卡', slot: slot }, 'photo')
        .then(function (res) { onOk(res.data); })
        .catch(onErr);
    } else {
      request('/checkins', { method: 'POST', data: { latitude: lat, longitude: lng, address: '小程序打卡', slot: slot } })
        .then(function (res) { onOk(res.data); })
        .catch(onErr);
    }
  }
});
