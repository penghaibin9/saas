/** 学生「我的档案」mock（08A 9.5） */
export const studentProfile = {
  base: {
    name: '张一鸣', studentNo: '2023100001', gender: '男', nation: '汉族',
    birth: '2005-03-18', political: '共青团员', idCard: '4301232005xxxx1234'
  },
  contact: {
    phone: '13612345678', email: 'linkx@example.edu.cn',
    address: '湖南省长沙市岳麓区xxxx', emergency: '林建国（父） 13700000009'
  },
  org: {
    college: '信息工程学院', major: '软件工程', className: '软件工程 2401 班',
    grade: '2024 级', system: '全日制本科', enrollDate: '2024-09-01'
  },
  status: { stageText: '在校', statusText: '正常在籍', enrollStatus: '已注册（2025-2026 秋）' },
  // 可申请更正字段 vs 不可修改字段（08A 9.5）
  editableFields: ['phone', 'address', 'emergency'],
  lockedFields: ['name', 'idCard', 'studentNo', 'status'],
  summaries: {
    service: '近 6 个月办理 8 项，均已办结',
    internship: '暂未进入实习阶段',
    graduation: '暂未进入毕业设计阶段',
    employment: '未开始就业去向填报'
  },
  credentials: [
    { id: 'cr1', name: '学生证', status: 'PUBLISHED', updated: '2024-09-05' },
    { id: 'cr2', name: '录取通知书', status: 'ARCHIVED', updated: '2024-08-20' },
    { id: 'cr3', name: '身份证（正反面）', status: 'APPROVED', updated: '2024-09-01' }
  ]
}
export default studentProfile
