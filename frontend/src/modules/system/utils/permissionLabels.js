// Display-only glossary. Never translate the permission keys sent to the API.
import catalog from '../../../../../shared/contracts/permission-catalog.json' with { type: 'json' }
const catalogLabels = new Map(catalog.entries.map(item => [item.permissionCode, item.label]))
const words = {
  deferredExam: '缓考', arrange: '安排', exemption: '免修', graduation: '毕业审核', majorSplit: '专业分流',
  quality: '教学质量', rectification: '整改', deferral: '缓注册', eligibility: '资格', resolve: '解决',
  unregistered: '未注册学生', scan: '扫描排查', retake: '重修', correction: '更正', availability: '可用时段',
  selection: '选课', lock: '锁定', rosterView: '查看名单', officeReview: '教务处审核', term: '学期',
  catalog: '目录', fee: '费用', warning: '预警', start: '启动', notify: '通知', secondRound: '二次答辩',
  appealReview: '申诉审核', calculate: '计算', guide: '指导', midterm: '中期检查', disputeReview: '异议审核',
  result: '结果', confirmOnBehalf: '代为确认', issue: '下发', execute: '执行', intake: '受理',
  conflict: '冲突', manual: '人工办理', peerEval: '同行评价', selfEval: '自我评价', supervisorEval: '督导评价',
  enroll: '选课报名', generate: '生成', school_confirm: '学校确认', blacklist: '黑名单', contact: '联系人',
  enterprise_by_student: '学生评价企业', position_by_student: '学生评价岗位', insufficient: '指导不足',
  recommend: '推荐', recheck: '复核', rectify: '整改',
  academicAffairs: '教务', studentAffairs: '学工', graduationDesign: '毕业设计', internship: '岗位实习',
  employment: '就业', system: '系统管理', systemAdmin: '系统管理', workbench: '工作台', workflow: '工作流',
  orientation: '迎新', student: '学生', academicCalendar: '校历', academicReview: '教务审核',
  accept: '验收', access: '访问', activate: '启用', activity: '活动', adjust: '调整', advisor: '指导教师',
  affiliation: '任职关系', agreement: '协议', aid: '困难认定', allocation: '分配', appeal: '申诉',
  application: '申请', apply: '应用', approval: '审批', approve: '审批', archive: '档案', assign: '分配',
  'assign-role': '分配角色', attendance: '考勤', audit: '审计', batch: '批次', bind: '绑定', brand: '学校品牌',
  cadre: '班干部', calendar: '校历', calendarArchive: '校历归档', calendarPublish: '校历发布', campus: '校区',
  campusService: '校园服务', cancelLeaveConfirm: '销假确认', change: '变更', changeStatus: '变更状态',
  check: '检查', class: '班级', classroom: '教室', classTimeBand: '上课时间段', close: '关闭', club: '社团',
  college: '学院', collegeReview: '学院审核', communication: '通信', company: '企业', complaint: '投诉',
  compliance: '合规', config: '配置', configure: '配置', confirm: '确认', consent: '知情同意',
  counselorEval: '辅导员考核', counselorReview: '辅导员审核', course: '课程', create: '新增', dashboard: '概览',
  dataCenter: '数据中心', dataExchange: '数据交换', defense: '答辩', delegation: '临时授权', delete: '删除',
  deliver: '送达', disburse: '发放', discipline: '处分', distribution: '分配', done: '完成', dorm: '宿舍',
  edit: '编辑', emergency: '紧急事项', enterprise: '企业', equipment: '设备', escalate: '升级处理',
  eval: '评价', evaluation: '评价', evidence: '证明材料', exam: '考试', exception: '异常', exempt: '免修',
  explain: '解释', export: '导出', extension: '延期', feature: '功能开关', field: '字段', file: '文件',
  fileGovernance: '文件治理', filing: '备案', final: '最终成果', followup: '跟进', force: '强制',
  funding: '奖助资助', grade: '成绩', gradeChange: '成绩更正', gradeRecognition: '成绩认定',
  graduationCert: '毕业证书', grant: '授予', groupManage: '分组管理', guidance: '指导', handle: '处理',
  home: '首页', homeSchool: '家校沟通', implementation: '实施验收', import: '导入', incident: '事件',
  input: '录入', inspection: '检查', installed: '已安装能力', insurance: '保险', integration: '系统集成',
  intention: '意向', job: '后台任务', lab: '实训室', league: '团学', leave: '请假', levelExam: '等级考试',
  lib: '资源库', lifecycle: '生命周期', loan: '助学贷款', log: '日志', login: '登录', major: '专业',
  makeup: '补考', manage: '管理', mapping: '映射', match: '匹配', material: '材料', mental: '心理',
  mentor: '导师', merge: '合并', message: '消息', migration: '数据迁移', more: '扩展功能', operation: '操作',
  order: '订单', org: '组织', overdue: '逾期', package: '资源包', payment: '缴费', permission: '权限',
  plagiarism: '查重', plan: '计划', policy: '策略', position: '岗位', preset: '预设', preview: '预览',
  process: '流程', profile: '个人档案', program: '培养方案', project: '项目', proposal: '开题',
  psyDetail: '心理敏感详情', publicity: '公示', publish: '发布', ranking: '排名', record: '记录',
  recordAbnormal: '登记异常', reduction: '费用减免', registration: '注册', relation: '关联关系',
  remove: '解除', reopen: '重新开启', report: '报告', request: '申请', resource: '资源',
  resourceConflict: '资源冲突', resourceOccupancy: '资源占用', resourceRepair: '资源报修', resourceStats: '资源统计',
  restore: '恢复', return: '退回', returned: '已退回', review: '审核', risk: '风险', riskArchive: '风险归档',
  role: '角色', rollback: '回滚', roster: '名单', round: '轮次', rule: '规则', run: '执行', safety: '安全',
  schedule: '排期', scheduleChange: '调停课', schoolAll: '全校人员', schoolConfirm: '学校确认',
  schoolStaff: '全校教职工', schoolStudent: '全校学生', scope: '数据范围', score: '评分', scoreConfirm: '成绩确认',
  security: '安全', self: '本人', sensitive: '敏感信息', sign: '签署', snapshot: '快照', statistics: '统计',
  stats: '统计', statusChange: '状态变更', submit: '提交', sync: '同步', talk: '谈心谈话', task: '任务',
  taskbook: '任务书', teacherConfirm: '教师确认', teachingTask: '教学任务', template: '模板', textbook: '教材',
  timeslot: '作息时间', todo: '待办', topic: '课题', transfer: '转交', unemployed: '未就业人员',
  update: '修改', user: '账号', verify: '核验', view: '查看', view_full: '查看完整信息', viewOwn: '查看本人数据',
  viewSensitive: '查看敏感信息', viewTenant: '查看本校数据', visit: '走访', void: '作废', withdraw: '撤回',
  workOrder: '工单', workstudy: '勤工助学', phoneBinding: '手机号凭据', lookup: '精确核对',
  candidate: '待验证号码', remind: '验证提醒', revoke: '撤销', recovery: '账号恢复',
}

export function permissionDisplayLabel(code, label) {
  if (label && /[\u3400-\u9fff]/u.test(label)) return label
  const registered = catalogLabels.get(code)
  if (registered && /[\u3400-\u9fff]/u.test(registered)) return registered
  const parts = String(code || '').split('.')
  return parts.every(part => words[part]) ? parts.map(part => words[part]).join(' · ') : '权限名称待维护'
}

const roles = {
  ACADEMIC_ADMIN: '教务管理员', ACADEMIC_TEACHER: '任课教师', COLLEGE_ADMIN: '学院管理员',
  COUNSELOR: '辅导员', DORM_MANAGER: '宿管老师', EMPLOYMENT_TEACHER: '就业老师', FUNDING_TEACHER: '资助老师',
  GD_COLLEGE_ADMIN: '学院毕设管理员', GD_DEFENSE_EXPERT: '答辩专家', GD_DEFENSE_SECRETARY: '答辩秘书',
  GD_GRADE_ADMIN: '毕设成绩管理员', GD_MAJOR_ADMIN: '专业毕设管理员', GD_MENTOR: '毕设指导教师',
  GD_REVIEWER: '毕设评阅教师', GRADUATION_ADMIN: '毕业设计管理员', INTERN_MENTOR: '实习指导教师',
  LEADER: '校领导', ORG_PERSONNEL: '组织人事人员', PSYCHOLOGY_TEACHER: '心理老师', SCHOOL_ADMIN: '学校管理员',
  SECURITY_AUDITOR: '安全审计员', STAFF: '教职工', STUDENT: '学生', STUDENT_AFFAIRS: '学工老师',
  STUDENT_AFFAIRS_ADMIN: '学工管理员', SYS_ADMIN: '系统管理员', YOUTH_LEAGUE: '团委老师',
}

export function roleDisplayLabel(code, label) {
  return label && /[\u3400-\u9fff]/u.test(label) ? label : roles[code] || '角色名称待维护'
}
