/**
 * 毕业论文（设计）规范流程基线。
 *
 * 这是系统的“流程骨架”，不是把某一学校手册中的期限、人数或分值写死。
 * 各批次仍通过阶段配置、评分规则和模板来落地本校口径。
 */
export const GRADUATION_MANUAL_WORKFLOW = [
  {
    key: 'topic',
    order: '01',
    title: '组织与选题',
    owner: '毕设管理员 / 指导小组',
    deliverable: '批次、学生名单、课题库、导师分配',
    gate: '一人一题，课题与培养目标匹配，导师容量合规',
    route: '/admin/graduation/topic-lib'
  },
  {
    key: 'taskbook',
    order: '02',
    title: '任务书确认',
    owner: '指导教师 → 学生',
    deliverable: '任务目标、研究内容、进度计划、成果要求',
    gate: '导师下达后由学生确认；变更保留版本记录',
    route: '/admin/graduation/process?panel=taskbook'
  },
  {
    key: 'proposal',
    order: '03',
    title: '开题论证',
    owner: '学生 → 导师 / 院系',
    deliverable: '开题报告、研究依据、技术路线、预期成果',
    gate: '开题审核通过后进入正式指导；退回必须整改重提',
    route: '/admin/graduation/proposals'
  },
  {
    key: 'guidance',
    order: '04',
    title: '过程指导',
    owner: '指导教师 / 学生',
    deliverable: '阶段总结、指导意见、问题与附件',
    gate: '按批次规则完成最低指导频次，形成可追溯记录',
    route: '/admin/graduation/process?panel=guidance'
  },
  {
    key: 'midterm',
    order: '05',
    title: '中期检查',
    owner: '指导教师 / 检查组',
    deliverable: '中期报告、检查结论、整改与复核',
    gate: '通过或整改复核通过；未完成者不能进入成果检查',
    route: '/admin/graduation/process?panel=midterm'
  },
  {
    key: 'final',
    order: '06',
    title: '成果检查',
    owner: '学生 → 评阅教师',
    deliverable: '定稿、查重记录、评阅意见、修改说明',
    gate: '格式、学术诚信与评阅均合格，才具备答辩资格',
    route: '/admin/graduation/finals'
  },
  {
    key: 'defense',
    order: '07',
    title: '答辩与评分',
    owner: '答辩秘书 / 答辩组',
    deliverable: '答辩安排、答辩记录、评委评分、二次答辩记录',
    gate: '资格审核通过后安排答辩；评分确认后进入成绩评定',
    route: '/admin/graduation/defense'
  },
  {
    key: 'archive',
    order: '08',
    title: '成绩归档与总结',
    owner: '院系 / 毕设管理员',
    deliverable: '最终成绩、完整材料包、批次总结',
    gate: '成绩发布与材料齐套后归档；缺件持续预警',
    route: '/admin/graduation/risk-archive?panel=archive'
  }
]

export const GRADUATION_MANUAL_GATES = [
  '批次规则决定具体期限、导师容量、指导次数和评分权重。',
  '每个阶段都必须留下责任人、时间、材料和审核/整改记录。',
  '上一关未通过时，系统应阻止或预警后续关键动作。'
]
