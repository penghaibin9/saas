const config = require('../../config');

Page({
  data: { tab: 'privacy', operatorName: '', privacyContact: '', schoolName: '', legalVersion: '' },
  onLoad(query) {
    this.setData({
      tab: query.tab === 'terms' ? 'terms' : 'privacy',
      operatorName: config.operatorName,
      privacyContact: config.privacyContact,
      schoolName: config.schoolName,
      legalVersion: config.legalVersion
    });
  },
  switchTab(e) { this.setData({ tab: e.currentTarget.dataset.tab }); }
});
