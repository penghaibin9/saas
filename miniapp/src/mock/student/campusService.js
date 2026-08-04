/**
 * 在校服务大厅目录（08A 七、服务中心）。
 * ⚠️ 2026-08-04 复审标记：categories/items 当前仍来自本静态文件，enrichCampusService()
 * 只覆盖 myRecords（本人请假/工单等真实记录），目录本身（是否上线、承办部门、是否需审批）
 * 从未与后端合并。若这只是早期示例数据，需迁移到后端租户服务目录；若产品确认这是全平台
 * 统一静态目录，应改名为正式配置并去掉个体状态断言，由后端校验稳定 serviceKey——
 * 这属于业务合同判断，需甲方/产品拍板，本次只先去掉下方"本学期已缴清"这类冒充个人事实的
 * 硬编码断言（对所有学生展示同一句已缴费结论是明确错误，不等待产品决策也应先修）。
 */
export const serviceCategories = [
  { key: 'academic', label: '教务服务', icon: '▤' },
  { key: 'affairs', label: '学工服务', icon: '♥' },
  { key: 'life', label: '生活服务', icon: '☕' },
  { key: 'finance', label: '财务服务', icon: '¥' }
]

export const serviceItems = [
  { id: 'sv1', name: '学生请假', cat: 'affairs', online: true, dept: '学工处', needApprove: true, available: true, desc: '事假/病假在线申请，辅导员审批' },
  { id: 'sv2', name: '在校证明开具', cat: 'academic', online: true, dept: '教务处', needApprove: true, available: true, desc: '在校证明、成绩证明等电子开具' },
  { id: 'sv3', name: '心理健康问卷', cat: 'affairs', online: true, dept: '心理中心', needApprove: false, available: true, desc: '本周必做，约 5 分钟' },
  { id: 'sv4', name: '实训室安全承诺书', cat: 'academic', online: true, dept: '实训中心', needApprove: false, available: true, desc: '进入实训室前须签署' },
  { id: 'sv5', name: '宿舍报修', cat: 'life', online: true, dept: '后勤中心', needApprove: false, available: true, desc: '水电、家具报修' },
  { id: 'sv6', name: '学费缴纳', cat: 'finance', online: true, dept: '财务处', needApprove: false, available: true, desc: '在线查询与缴纳学费/住宿费' },
  { id: 'sv7', name: '奖助学金申请', cat: 'finance', online: true, dept: '资助中心', needApprove: true, available: true, desc: '国家/学校奖助学金' },
  { id: 'sv8', name: '第二课堂学分认定', cat: 'academic', online: true, dept: '校团委', needApprove: true, available: true, desc: '志愿/竞赛/社会实践学分' }
]
export default { serviceCategories, serviceItems }
