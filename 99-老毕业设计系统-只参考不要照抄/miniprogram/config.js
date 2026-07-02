/**
 * 小程序运行配置（上线前主要修改这个文件）。
 *
 * develop：微信开发者工具 / 开发版
 * trial：体验版
 * release：正式版
 */
module.exports = {
  schoolName: '示范院校',
  graduationYear: new Date().getFullYear(),
  operatorName: '请填写运营主体全称',
  privacyContact: '请填写个人信息保护联系人及邮箱/电话',
  // 开发环境保留演示快捷账号；体验版/正式版默认隐藏。
  demoAccounts: { develop: true, trial: false, release: false },
  legalVersion: '2026-07-01',

  apiBase: {
    develop: 'http://localhost:3000/api',
    // 真机无法访问电脑上的 localhost；体验版和正式版都应使用同一个 HTTPS 域名。
    trial: 'https://api.example.com/api',
    release: 'https://api.example.com/api'
  }
};
