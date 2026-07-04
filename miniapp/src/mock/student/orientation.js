/** 迎新报到 mock（08A 5.2）。此学生已完成报到，展示时间线 + 完成态。 */
export const studentOrientation = {
  batch: '2024 级本科新生报到',
  overallStatus: 'REGISTERED',
  overallText: '已完成报到 · 待/已注册',
  reportCode: { code: 'XY-2024-0612', valid: false, note: '报到已完成，报到码已失效' },
  steps: [
    { id: 's1', title: '账号激活', status: 'COMPLETED', time: '2024-08-18', desc: '统一身份认证已激活' },
    { id: 's2', title: '身份核验（人脸）', status: 'COMPLETED', time: '2024-08-19', desc: '核验通过' },
    { id: 's3', title: '预报到信息采集', status: 'COMPLETED', time: '2024-08-22', desc: '基础信息、家庭信息已提交' },
    { id: 's4', title: '缴费', status: 'COMPLETED', time: '2024-08-25', desc: '学费/住宿费已缴清' },
    { id: 's5', title: '绿色通道', status: 'ARCHIVED', time: '—', desc: '未申请' },
    { id: 's6', title: '宿舍分配', status: 'COMPLETED', time: '2024-08-28', desc: '梅园 6 栋 412' },
    { id: 's7', title: '现场报到 / 物资领取', status: 'COMPLETED', time: '2024-09-01', desc: '军训服、床上用品已领取' },
    { id: 's8', title: '学籍注册同步', status: 'COMPLETED', time: '2024-09-06', desc: '学籍已同步' }
  ],
  contacts: [
    { role: '辅导员', name: '周敏', phone: '13800000001' },
    { role: '招生咨询', name: '招生办', phone: '0731-8888xxxx' }
  ]
}
export default studentOrientation
