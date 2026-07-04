/**
 * 数据中心（数据驾驶舱）mock 数据（与 mocks/internship 同一世界观：演示职业技术学院）。
 * 自洽性约定（校验过的口径）：
 *  - 生命周期漏斗（2023 级 / 2026 届，1620 人）各阶段人数逐级递减；
 *  - 学院排行学生数合计 = 在册学生总数 4520，学院风险数合计 = 风险总量 114；
 *  - 就业去向落实 1147 = 签约 862 + 升学 203 + 参军 37 + 创业 45，落实率 70.8% = 1147 / 1620；
 *  - 概览指标「待处理风险预警 47」与风险统计 byStatus 待处理 47 一致。
 * 页面禁止直接 import 本文件，必须经 modules/dataCenter/api/dataCenter.api 获取。
 */

export const tenantBrandConfig = {
  tenantId: 'tenant-demo-a',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '',
  schoolBadge: '',
  brandColor: '#2563eb',
  watermarkText: '演示职业技术学院 · 内部数据'
}

/** mock 内部运行态：当前演示角色（经 api.switchRole 切换，仅用于演示角色差异） */
export const mockRuntime = { activeRoleCode: 'PRINCIPAL' }

/**
 * 权限动作全集模板（visible=false 时入口不渲染；allowed=false 且 visible=true 时置灰并提示 reason）。
 * 各角色档案在此模板之上做差异化收敛，见 roleProfiles。
 */
export const permissionActions = {
  viewDashboard: { visible: true, allowed: true, reason: '' },
  viewLifecycle: { visible: true, allowed: true, reason: '' },
  viewRankings: { visible: true, allowed: true, reason: '' },
  viewRisk: { visible: true, allowed: true, reason: '' },
  viewReports: { visible: true, allowed: true, reason: '' },
  exportOverview: { visible: true, allowed: true, reason: '' },
  exportLifecycle: { visible: true, allowed: true, reason: '' },
  exportRanking: { visible: true, allowed: true, reason: '' },
  exportRisk: { visible: true, allowed: true, reason: '' },
  exportReport: { visible: true, allowed: true, reason: '' },
  drilldownStudents: { visible: true, allowed: true, reason: '' },
  batchRemind: { visible: true, allowed: true, reason: '' },
  createReport: { visible: true, allowed: true, reason: '' },
  editReport: { visible: true, allowed: true, reason: '' },
  voidReport: { visible: true, allowed: true, reason: '' },
  viewAuditLog: { visible: true, allowed: true, reason: '' }
}

function buildActions(overrides = {}) {
  const out = {}
  Object.keys(permissionActions).forEach((key) => {
    out[key] = { ...permissionActions[key], ...(overrides[key] || {}) }
  })
  return out
}

const ALL_METRIC_KEYS = [
  'studentTotal',
  'orientationRate',
  'serviceRate',
  'academicWarning',
  'internshipOnboardRate',
  'graduationPassRate',
  'employmentRate',
  'riskPending'
]

/**
 * 5 个演示角色档案：可见指标与权限按钮必须有差异 ——
 *  - 校级领导 / 系统管理员：可导出全校概览；校级领导默认不看学生明细（聚合视图）；
 *  - 学院管理员：数据范围收敛到本学院，不可导出全校概览；
 *  - 教务老师：不看就业域指标，概览导出入口不可见；
 *  - 就业老师：不看教学域指标，且无权访问专题报表模块（用于演示无权限页）。
 */
export const roleProfiles = {
  PRINCIPAL: {
    currentRole: { userId: 'u-901', userName: '沈国华', roleCode: 'PRINCIPAL', roleName: '校级领导' },
    dataScope: { scopeCode: 'SCHOOL_ALL', scopeName: '全校（5 个学院 · 4520 人）' },
    visibleMetricKeys: [...ALL_METRIC_KEYS],
    permissionActions: buildActions({
      drilldownStudents: { allowed: false, reason: '校级视图默认仅呈现聚合数据，查看学生明细需另行开通数据授权' },
      batchRemind: { allowed: false, reason: '提醒建议由学院管理员与责任教师发起，校级视图仅查看' },
      createReport: { allowed: false, reason: '报表配置由「系统管理员」统一维护' },
      editReport: { allowed: false, reason: '编辑报表配置需「系统管理员」角色' },
      voidReport: { visible: false, allowed: false, reason: '作废操作仅系统管理员可见' }
    })
  },
  COLLEGE_ADMIN: {
    currentRole: { userId: 'u-902', userName: '陈立群', roleCode: 'COLLEGE_ADMIN', roleName: '学院管理员' },
    dataScope: { scopeCode: 'COLLEGE_IT', scopeName: '信息工程学院（1286 人）' },
    visibleMetricKeys: [...ALL_METRIC_KEYS],
    permissionActions: buildActions({
      exportOverview: { allowed: false, reason: '全校概览导出仅限校级领导与系统管理员' },
      createReport: { allowed: false, reason: '新增报表配置需「系统管理员」角色' },
      editReport: { allowed: false, reason: '编辑报表配置需「系统管理员」角色' },
      voidReport: { visible: false, allowed: false, reason: '作废操作仅系统管理员可见' }
    })
  },
  ACADEMIC: {
    currentRole: { userId: 'u-903', userName: '苏婉晴', roleCode: 'ACADEMIC', roleName: '教务老师' },
    dataScope: { scopeCode: 'ACADEMIC_DOMAIN', scopeName: '全校教学域数据' },
    visibleMetricKeys: [
      'studentTotal',
      'orientationRate',
      'serviceRate',
      'academicWarning',
      'graduationPassRate',
      'riskPending'
    ],
    permissionActions: buildActions({
      exportOverview: { visible: false, allowed: false, reason: '全校概览导出入口对教务老师不可见' },
      exportRanking: { allowed: false, reason: '排行数据导出需学院管理员及以上角色' },
      createReport: { visible: false, allowed: false, reason: '报表配置入口仅系统管理员可见' },
      editReport: { visible: false, allowed: false, reason: '报表配置入口仅系统管理员可见' },
      voidReport: { visible: false, allowed: false, reason: '作废操作仅系统管理员可见' }
    })
  },
  EMPLOYMENT: {
    currentRole: { userId: 'u-904', userName: '韩东升', roleCode: 'EMPLOYMENT', roleName: '就业老师' },
    dataScope: { scopeCode: 'EMPLOYMENT_DOMAIN', scopeName: '全校就业域数据（2026 届）' },
    visibleMetricKeys: ['studentTotal', 'internshipOnboardRate', 'employmentRate', 'riskPending'],
    permissionActions: buildActions({
      viewReports: { allowed: false, reason: '就业老师暂未开通专题报表模块权限，如需使用请联系系统管理员' },
      exportOverview: { visible: false, allowed: false, reason: '全校概览导出入口对就业老师不可见' },
      exportLifecycle: { allowed: false, reason: '生命周期全量统计导出需学院管理员及以上角色' },
      exportRanking: { allowed: false, reason: '排行数据导出需学院管理员及以上角色' },
      exportReport: { visible: false, allowed: false, reason: '专题报表模块未开通' },
      createReport: { visible: false, allowed: false, reason: '专题报表模块未开通' },
      editReport: { visible: false, allowed: false, reason: '专题报表模块未开通' },
      voidReport: { visible: false, allowed: false, reason: '专题报表模块未开通' }
    })
  },
  SYS_ADMIN: {
    currentRole: { userId: 'u-905', userName: '方远', roleCode: 'SYS_ADMIN', roleName: '系统管理员' },
    dataScope: { scopeCode: 'PLATFORM_ALL', scopeName: '全校（含平台配置域）' },
    visibleMetricKeys: [...ALL_METRIC_KEYS],
    permissionActions: buildActions({})
  }
}

export const statusOptions = {
  reportStatus: [
    { value: 'DRAFT', label: '草稿' },
    { value: 'PUBLISHED', label: '已发布' },
    { value: 'ARCHIVED', label: '已归档' },
    { value: 'VOIDED', label: '已作废' }
  ],
  reportCycles: [
    { value: 'MONTHLY', label: '月度' },
    { value: 'QUARTERLY', label: '季度' },
    { value: 'ONCE', label: '一次性' }
  ],
  riskLevel: [
    { value: 'HIGH', label: '高风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'LOW', label: '低风险' }
  ],
  lifecycleStages: [
    { value: 'ORIENTATION', label: '迎新报到' },
    { value: 'SERVICE', label: '在校服务' },
    { value: 'ACADEMIC', label: '学业过程' },
    { value: 'INTERNSHIP', label: '岗位实习' },
    { value: 'GRADUATION', label: '毕业设计' },
    { value: 'EMPLOYMENT', label: '就业去向' }
  ]
}

export const filterOptions = {
  colleges: [
    { value: 'col-01', label: '信息工程学院' },
    { value: 'col-02', label: '智能制造学院' },
    { value: 'col-03', label: '商贸管理学院' },
    { value: 'col-04', label: '建筑工程学院' },
    { value: 'col-05', label: '现代服务学院' }
  ],
  majors: [
    { value: 'maj-01', label: '软件技术', collegeId: 'col-01' },
    { value: 'maj-02', label: '大数据技术', collegeId: 'col-01' },
    { value: 'maj-03', label: '计算机网络技术', collegeId: 'col-01' },
    { value: 'maj-04', label: '数字媒体技术', collegeId: 'col-01' },
    { value: 'maj-05', label: '机电一体化技术', collegeId: 'col-02' },
    { value: 'maj-06', label: '电子商务', collegeId: 'col-03' }
  ],
  classes: [
    { value: 'cls-2301', label: '软件2301' },
    { value: 'cls-2302', label: '软件2302' },
    { value: 'cls-2303', label: '软件2303' },
    { value: 'cls-2304', label: '软件2304' }
  ],
  grades: [
    { value: 'g2023', label: '2023 级' },
    { value: 'g2024', label: '2024 级' },
    { value: 'g2025', label: '2025 级' }
  ],
  timeRanges: [
    { value: 'LAST_6M', label: '近 6 个月' },
    { value: 'THIS_TERM', label: '本学期' },
    { value: 'THIS_YEAR', label: '本学年' }
  ],
  calibers: [
    { value: 'REGISTERED', label: '在册口径' },
    { value: 'NATURAL', label: '自然口径' }
  ],
  rankLevels: [
    { value: 'COLLEGE', label: '按学院' },
    { value: 'MAJOR', label: '按专业' },
    { value: 'CLASS', label: '按班级' }
  ],
  reportCategories: [
    { value: 'EMPLOYMENT', label: '就业质量' },
    { value: 'INTERNSHIP', label: '实习过程' },
    { value: 'ACADEMIC', label: '教学质量' },
    { value: 'SERVICE', label: '校园服务' },
    { value: 'RISK', label: '风险治理' }
  ],
  riskSources: [
    { value: 'INTERNSHIP', label: '岗位实习' },
    { value: 'ACADEMIC', label: '学业过程' },
    { value: 'SERVICE', label: '在校服务' },
    { value: 'GRADUATION', label: '毕业设计' },
    { value: 'EMPLOYMENT', label: '就业去向' },
    { value: 'ORIENTATION', label: '迎新报到' }
  ]
}

export const exportOptions = {
  scopes: [
    { value: 'OVERVIEW', label: '全校概览数据' },
    { value: 'LIFECYCLE', label: '生命周期统计' },
    { value: 'RANKING', label: '排行分析数据' },
    { value: 'RISK', label: '风险预警报表' },
    { value: 'REPORT', label: '专题报表数据' }
  ],
  purposes: [
    { value: 'REPORT_TO_LEADER', label: '向上级汇报', desc: '用于校内决策会议或上级领导汇报材料' },
    { value: 'INTERNAL_ANALYSIS', label: '校内分析', desc: '用于教学、就业等职能部门的过程分析' },
    { value: 'EDU_BUREAU', label: '教育主管部门报送', desc: '用于人才培养质量年报等法定报送场景' },
    { value: 'ARCHIVE', label: '归档备查', desc: '用于周期性数据归档与审计备查' }
  ],
  policyNote: '所有导出默认执行字段脱敏并叠加追踪水印，导出任务、用途与操作人一并写入审计日志'
}

/**
 * 概览指标（按统计口径分组）：
 *  - 在册口径：仅统计学籍在册学生；
 *  - 自然口径：含休学、保留学籍与入学资格保留学生（2026 届自然口径 1655 人）。
 */
export const overviewMetrics = {
  REGISTERED: {
    caliber: 'REGISTERED',
    caliberLabel: '在册口径',
    caliberNote: '在册口径 = 学籍状态为「在册」的学生；比率类指标分母均为对应在册群体',
    updatedAt: '2026-07-03 06:00',
    stageFlow: [
      { label: '迎新报到', value: 1602 },
      { label: '在校服务', value: 1586 },
      { label: '学业过程', value: 1544 },
      { label: '岗位实习', value: 1360, active: true },
      { label: '毕业设计', value: 1312 },
      { label: '就业去向', value: 1147 }
    ],
    metrics: [
      {
        key: 'studentTotal',
        label: '在册学生总数',
        value: '4520',
        unit: '人',
        trend: '较上月 +36',
        trendQuality: 'neutral',
        sourceModule: '学生主档',
        description: '全校学籍状态为「在册」的学生数，学籍异动审批通过后次日生效',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'orientationRate',
        label: '迎新报到率',
        value: '97.7',
        unit: '%',
        trend: '较去年同期 +1.2pp',
        trendQuality: 'good',
        sourceModule: '迎新报到',
        description: '2025 级新生 1580 人中完成报到 1544 人，未报到 36 人已转辅导员跟进',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'serviceRate',
        label: '服务工单按时办结率',
        value: '96.4',
        unit: '%',
        trend: '较上月 +0.8pp',
        trendQuality: 'good',
        sourceModule: '在校服务',
        description: '本学年服务工单 8642 件，按 SLA 时限办结 8331 件，超时 31 件在案',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'academicWarning',
        label: '学业预警在案学生',
        value: '128',
        unit: '人',
        trend: '较上学期 -14',
        trendQuality: 'good',
        sourceModule: '学业过程',
        description: '两门及以上课程不及格或学分进度滞后触发预警，帮扶结案后自动移出',
        drillRoute: '/admin/data-center/risk',
        drillLabel: '风险预警数据'
      },
      {
        key: 'internshipOnboardRate',
        label: '实习在岗率',
        value: '92.6',
        unit: '%',
        trend: '较上月 -1.1pp',
        trendQuality: 'bad',
        sourceModule: '岗位实习',
        description: '2026 届应在岗 1360 人，当前在岗 1259 人；请假旁路与待上岗不计入在岗',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'graduationPassRate',
        label: '毕设一次通过率',
        value: '89.3',
        unit: '%',
        trend: '较上届 +2.4pp',
        trendQuality: 'good',
        sourceModule: '毕业设计',
        description: '查重与评审一次通过人数 / 已提交人数，重交后通过不计入一次通过',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'employmentRate',
        label: '2026 届去向落实率',
        value: '70.8',
        unit: '%',
        trend: '较上月 +6.3pp',
        trendQuality: 'good',
        sourceModule: '就业去向',
        description: '去向落实 1147 人（签约 862 / 升学 203 / 参军 37 / 创业 45）/ 在册 1620 人',
        drillRoute: '/admin/data-center/rankings',
        drillLabel: '排行分析'
      },
      {
        key: 'riskPending',
        label: '待处理风险预警',
        value: '47',
        unit: '条',
        trend: '今日新增 5',
        trendQuality: 'bad',
        sourceModule: '风险预警',
        description: '各业务模块预警规则命中且尚未领取处理的风险记录，超 72 小时未处理将升级',
        drillRoute: '/admin/data-center/risk',
        drillLabel: '风险预警数据'
      }
    ]
  },
  NATURAL: {
    caliber: 'NATURAL',
    caliberLabel: '自然口径',
    caliberNote: '自然口径 = 在册学生 + 休学 / 保留学籍 / 保留入学资格学生（2026 届 1655 人），用于对外报送对齐',
    updatedAt: '2026-07-03 06:00',
    stageFlow: [
      { label: '迎新报到', value: 1611 },
      { label: '在校服务', value: 1593 },
      { label: '学业过程', value: 1549 },
      { label: '岗位实习', value: 1362, active: true },
      { label: '毕业设计', value: 1313 },
      { label: '就业去向', value: 1147 }
    ],
    metrics: [
      {
        key: 'studentTotal',
        label: '自然口径学生总数',
        value: '4586',
        unit: '人',
        trend: '含休学等 66 人',
        trendQuality: 'neutral',
        sourceModule: '学生主档',
        description: '在册 4520 人 + 休学 41 人 + 保留学籍 18 人 + 保留入学资格 7 人',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'orientationRate',
        label: '迎新报到率',
        value: '96.6',
        unit: '%',
        trend: '较去年同期 +0.9pp',
        trendQuality: 'good',
        sourceModule: '迎新报到',
        description: '分母含放弃入学 18 人：报到 1544 / 自然口径新生 1598',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'serviceRate',
        label: '服务工单按时办结率',
        value: '96.4',
        unit: '%',
        trend: '与在册口径一致',
        trendQuality: 'neutral',
        sourceModule: '在校服务',
        description: '服务工单统计不区分口径，与在册口径数值一致',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'academicWarning',
        label: '学业预警在案学生',
        value: '131',
        unit: '人',
        trend: '含复学过渡期 3 人',
        trendQuality: 'neutral',
        sourceModule: '学业过程',
        description: '在册预警 128 人 + 休学复学过渡期挂起预警 3 人',
        drillRoute: '/admin/data-center/risk',
        drillLabel: '风险预警数据'
      },
      {
        key: 'internshipOnboardRate',
        label: '实习在岗率',
        value: '91.6',
        unit: '%',
        trend: '较上月 -1.2pp',
        trendQuality: 'bad',
        sourceModule: '岗位实习',
        description: '自然口径应在岗 1374 人（含休学返岗过渡 14 人），当前在岗 1259 人',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'graduationPassRate',
        label: '毕设一次通过率',
        value: '88.7',
        unit: '%',
        trend: '较上届 +2.1pp',
        trendQuality: 'good',
        sourceModule: '毕业设计',
        description: '分母含延期提交学生，口径较在册口径略低',
        drillRoute: '/admin/data-center/lifecycle',
        drillLabel: '生命周期总览'
      },
      {
        key: 'employmentRate',
        label: '2026 届去向落实率',
        value: '69.3',
        unit: '%',
        trend: '较上月 +6.0pp',
        trendQuality: 'good',
        sourceModule: '就业去向',
        description: '去向落实 1147 人 / 自然口径 1655 人（教育主管部门报送口径）',
        drillRoute: '/admin/data-center/rankings',
        drillLabel: '排行分析'
      },
      {
        key: 'riskPending',
        label: '待处理风险预警',
        value: '47',
        unit: '条',
        trend: '今日新增 5',
        trendQuality: 'bad',
        sourceModule: '风险预警',
        description: '风险预警不区分统计口径，与在册口径数值一致',
        drillRoute: '/admin/data-center/risk',
        drillLabel: '风险预警数据'
      }
    ]
  }
}

/** 学生生命周期漏斗（2023 级 / 2026 届毕业年级，在册 1620 人，各阶段逐级递减） */
export const lifecycleFunnel = {
  cohortLabel: '2023 级（2026 届）',
  totalCount: 1620,
  updatedAt: '2026-07-03 06:00',
  stages: [
    {
      key: 'ORIENTATION',
      label: '迎新报到',
      count: 1602,
      rate: 98.9,
      abnormal: 18,
      note: '未按期报到 18 人，其中 12 人已补办、6 人转辅导员跟进'
    },
    {
      key: 'SERVICE',
      label: '在校服务',
      count: 1586,
      rate: 97.9,
      abnormal: 16,
      note: '存在超时服务工单或宿舍异动未闭环的学生 16 人'
    },
    {
      key: 'ACADEMIC',
      label: '学业过程',
      count: 1544,
      rate: 95.3,
      abnormal: 42,
      note: '学业预警未结案 42 人，已全部建立帮扶记录'
    },
    {
      key: 'INTERNSHIP',
      label: '岗位实习',
      count: 1360,
      rate: 84.0,
      abnormal: 57,
      note: '打卡异常、超期未到岗等实习过程异常 57 人'
    },
    {
      key: 'GRADUATION',
      label: '毕业设计',
      count: 1312,
      rate: 81.0,
      abnormal: 48,
      note: '开题 / 中期 / 查重任一环节滞后 48 人'
    },
    {
      key: 'EMPLOYMENT',
      label: '就业去向',
      count: 1147,
      rate: 70.8,
      abnormal: 165,
      note: '毕业去向尚未落实且近 14 天无求职动态 165 人'
    }
  ]
}

export const orientationStats = {
  title: '迎新报到（2025 级新生）',
  scopeNote: '全校口径 · 2025 级秋季迎新',
  items: [
    { label: '应报到新生', value: '1580 人' },
    { label: '完成报到', value: '1544 人（97.7%）' },
    { label: '线上预报到率', value: '93.4%' },
    { label: '绿色通道办理', value: '76 人' },
    { label: '未报到跟进中', value: '36 人' }
  ]
}

export const serviceStats = {
  title: '在校服务（本学年）',
  scopeNote: '全校口径 · 2025-2026 学年',
  items: [
    { label: '服务工单累计', value: '8642 件' },
    { label: '按时办结率', value: '96.4%' },
    { label: '超时工单在案', value: '31 件' },
    { label: '服务满意度', value: '4.6 / 5.0' },
    { label: '宿舍异动办理', value: '412 件' }
  ]
}

export const academicStats = {
  title: '学业过程（全校在校生）',
  scopeNote: '全校口径 · 本学期',
  items: [
    { label: '学业预警在案', value: '128 人' },
    { label: '课程平均及格率', value: '92.4%' },
    { label: '补考待安排', value: '214 人次' },
    { label: '技能证书获取率', value: '78.6%' },
    { label: '帮扶结案率', value: '81.2%' }
  ]
}

export const internshipStats = {
  title: '岗位实习（2026 届）',
  scopeNote: '全校口径 · 2026 届春季批次',
  items: [
    { label: '应在岗学生', value: '1360 人' },
    { label: '当前在岗', value: '1259 人（92.6%）' },
    { label: '今日打卡率', value: '95.2%' },
    { label: '待处理打卡异常', value: '23 条' },
    { label: '实习风险学生', value: '34 人' }
  ]
}

export const graduationStats = {
  title: '毕业设计（2026 届）',
  scopeNote: '全校口径 · 2026 届',
  items: [
    { label: '开题通过', value: '1312 人' },
    { label: '中期检查通过率', value: '91.5%' },
    { label: '查重一次通过率', value: '89.3%' },
    { label: '答辩待安排', value: '118 人' },
    { label: '环节滞后学生', value: '48 人' }
  ]
}

export const employmentStats = {
  title: '就业去向（2026 届）',
  scopeNote: '全校口径 · 截至 07-03',
  items: [
    { label: '去向落实', value: '1147 人（70.8%）' },
    { label: '签约就业', value: '862 人' },
    { label: '升学', value: '203 人' },
    { label: '参军入伍', value: '37 人' },
    { label: '自主创业', value: '45 人' },
    { label: '待落实', value: '473 人' }
  ]
}

/** 风险预警统计：来源 / 等级 / 处理进度三个维度合计一致（114 条） */
export const riskStats = {
  updatedAt: '2026-07-03 06:00',
  total: 114,
  bySource: [
    { moduleCode: 'INTERNSHIP', moduleName: '岗位实习', count: 34 },
    { moduleCode: 'ACADEMIC', moduleName: '学业过程', count: 28 },
    { moduleCode: 'SERVICE', moduleName: '在校服务', count: 19 },
    { moduleCode: 'GRADUATION', moduleName: '毕业设计', count: 15 },
    { moduleCode: 'EMPLOYMENT', moduleName: '就业去向', count: 12 },
    { moduleCode: 'ORIENTATION', moduleName: '迎新报到', count: 6 }
  ],
  byLevel: [
    { level: 'HIGH', label: '高风险', count: 18 },
    { level: 'MEDIUM', label: '中风险', count: 41 },
    { level: 'LOW', label: '低风险', count: 55 }
  ],
  byStatus: [
    { key: 'PENDING', label: '待处理', count: 47 },
    { key: 'PROCESSING', label: '跟进中', count: 39 },
    { key: 'CLOSED', label: '本月已关闭', count: 28 }
  ],
  trend: {
    months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
    total: [86, 94, 102, 97, 108, 114],
    high: [9, 11, 14, 12, 16, 18]
  },
  suggestion: '实习类风险连续 3 个月居首，建议对在岗率低于 90% 的学院开展专项巡检'
}

/** 排行数据：学院学生数合计 = 4520；信息工程学院各专业合计 = 1286；软件技术 2023 级各班合计 = 162 */
export const collegeRankings = {
  level: 'COLLEGE',
  scopeName: '全校 5 个学院',
  totalCount: 4520,
  note: '综合完成率 = 生命周期六阶段加权完成度；较上期为月度名次变化',
  rows: [
    { id: 'col-01', rank: 1, name: '信息工程学院', studentCount: 1286, completionRate: 93.1, employmentRate: 74.2, riskCount: 31, delta: '▲ 1', deltaQuality: 'good' },
    { id: 'col-02', rank: 2, name: '智能制造学院', studentCount: 1052, completionRate: 91.8, employmentRate: 72.5, riskCount: 26, delta: '▼ 1', deltaQuality: 'bad' },
    { id: 'col-03', rank: 3, name: '商贸管理学院', studentCount: 936, completionRate: 90.6, employmentRate: 69.8, riskCount: 22, delta: '—', deltaQuality: 'neutral' },
    { id: 'col-04', rank: 4, name: '建筑工程学院', studentCount: 704, completionRate: 88.9, employmentRate: 66.4, riskCount: 19, delta: '▲ 1', deltaQuality: 'good' },
    { id: 'col-05', rank: 5, name: '现代服务学院', studentCount: 542, completionRate: 87.2, employmentRate: 64.1, riskCount: 16, delta: '▼ 1', deltaQuality: 'bad' }
  ]
}

export const majorRankings = {
  level: 'MAJOR',
  scopeName: '信息工程学院 4 个专业',
  totalCount: 1286,
  note: '专业排行默认展示信息工程学院（演示数据集），学生数合计等于学院在册数',
  rows: [
    { id: 'maj-01', rank: 1, name: '软件技术', studentCount: 486, completionRate: 94.6, employmentRate: 76.8, riskCount: 12, delta: '—', deltaQuality: 'neutral' },
    { id: 'maj-02', rank: 2, name: '大数据技术', studentCount: 352, completionRate: 92.9, employmentRate: 73.4, riskCount: 8, delta: '▲ 1', deltaQuality: 'good' },
    { id: 'maj-03', rank: 3, name: '计算机网络技术', studentCount: 268, completionRate: 91.2, employmentRate: 71.6, riskCount: 7, delta: '▼ 1', deltaQuality: 'bad' },
    { id: 'maj-04', rank: 4, name: '数字媒体技术', studentCount: 180, completionRate: 89.8, employmentRate: 68.9, riskCount: 4, delta: '—', deltaQuality: 'neutral' }
  ]
}

export const classRankings = {
  level: 'CLASS',
  scopeName: '软件技术专业 · 2023 级 4 个班',
  totalCount: 162,
  note: '班级排行默认展示软件技术 2023 级（毕业年级，风险与就业指标最活跃）',
  rows: [
    { id: 'cls-2301', rank: 1, name: '软件2301', studentCount: 42, completionRate: 95.8, employmentRate: 78.6, riskCount: 3, delta: '▲ 1', deltaQuality: 'good' },
    { id: 'cls-2302', rank: 2, name: '软件2302', studentCount: 40, completionRate: 94.5, employmentRate: 76.2, riskCount: 4, delta: '▼ 1', deltaQuality: 'bad' },
    { id: 'cls-2303', rank: 3, name: '软件2303', studentCount: 41, completionRate: 93.7, employmentRate: 75.5, riskCount: 2, delta: '—', deltaQuality: 'neutral' },
    { id: 'cls-2304', rank: 4, name: '软件2304', studentCount: 39, completionRate: 92.1, employmentRate: 73.8, riskCount: 3, delta: '—', deltaQuality: 'neutral' }
  ]
}

/** 近 6 个月趋势序列（月末快照，07 为当前月截至 07-03） */
export const trendCharts = [
  {
    key: 'employmentRate',
    label: '2026 届去向落实率',
    unit: '%',
    months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
    values: [41.2, 48.6, 55.4, 61.9, 66.5, 70.8]
  },
  {
    key: 'internshipOnboard',
    label: '实习在岗人数',
    unit: '人',
    months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
    values: [1180, 1224, 1246, 1231, 1268, 1259]
  },
  {
    key: 'riskTotal',
    label: '风险预警总量',
    unit: '条',
    months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
    values: [86, 94, 102, 97, 108, 114]
  },
  {
    key: 'serviceRate',
    label: '服务工单按时办结率',
    unit: '%',
    months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
    values: [95.1, 95.6, 96.0, 95.8, 96.2, 96.4]
  }
]

/**
 * 下钻学生清单（重点关注学生样本，字段在页面展示时脱敏）。
 * metricKeys：该生命中的指标 / 阶段标签；collegeId / majorId / classId 供排行下钻过滤。
 */
export const drilldownStudents = [
  {
    id: 'dd-001', name: '赵一凡', studentNo: 'S2026-000001', phone: '13512346867',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2301',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2301',
    stageLabel: '岗位实习', statusLabel: '连续 3 天打卡异常', tone: 'danger', riskLevel: 'HIGH',
    lastEvent: '07-02 打卡超范围（待核实）', metricKeys: ['INTERNSHIP', 'RISK', 'RANKING']
  },
  {
    id: 'dd-002', name: '林晓彤', studentNo: 'S2026-000006', phone: '15912348873',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2301',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2301',
    stageLabel: '岗位实习', statusLabel: '在岗正常', tone: 'success', riskLevel: 'NONE',
    lastEvent: '07-01 第 4 周周报已提交', metricKeys: ['INTERNSHIP', 'RANKING']
  },
  {
    id: 'dd-003', name: '陈志远', studentNo: 'S2026-000007', phone: '13712345460',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2302',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2302',
    stageLabel: '岗位实习', statusLabel: '请假旁路 · 情绪波动跟进', tone: 'warning', riskLevel: 'MEDIUM',
    lastEvent: '06-28 辅导员已联系家长', metricKeys: ['INTERNSHIP', 'RISK', 'RANKING']
  },
  {
    id: 'dd-004', name: '孙一诺', studentNo: 'S2026-000008', phone: '18612340031',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2302',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2302',
    stageLabel: '岗位实习', statusLabel: '超期未到岗', tone: 'danger', riskLevel: 'MEDIUM',
    lastEvent: '06-25 触发超期未到岗预警', metricKeys: ['INTERNSHIP', 'RISK', 'RANKING']
  },
  {
    id: 'dd-005', name: '周雨萌', studentNo: 'S2026-000009', phone: '15012347788',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2301',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2301',
    stageLabel: '毕业设计', statusLabel: '中期检查已通过', tone: 'success', riskLevel: 'NONE',
    lastEvent: '06-30 提交查重初稿', metricKeys: ['GRADUATION', 'RANKING']
  },
  {
    id: 'dd-006', name: '吴俊杰', studentNo: 'S2026-000010', phone: '13812349921',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2301',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2301',
    stageLabel: '毕业设计', statusLabel: '查重复核中', tone: 'warning', riskLevel: 'LOW',
    lastEvent: '07-01 查重率 18.4% 待复核', metricKeys: ['GRADUATION', 'RISK', 'RANKING']
  },
  {
    id: 'dd-007', name: '郑浩然', studentNo: 'S2026-000011', phone: '13312340276',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2302',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2302',
    stageLabel: '就业去向', statusLabel: '已签约（星辰网络）', tone: 'success', riskLevel: 'NONE',
    lastEvent: '06-26 三方协议归档', metricKeys: ['EMPLOYMENT', 'RANKING']
  },
  {
    id: 'dd-008', name: '何雨珊', studentNo: 'S2026-000012', phone: '15512340049',
    collegeId: 'col-01', majorId: 'maj-01', classId: 'cls-2301',
    collegeName: '信息工程学院', majorName: '软件技术', className: '软件2301',
    stageLabel: '就业去向', statusLabel: '待落实 · 近 14 天无求职动态', tone: 'warning', riskLevel: 'LOW',
    lastEvent: '06-18 最近一次投递记录', metricKeys: ['EMPLOYMENT', 'RISK', 'RANKING']
  },
  {
    id: 'dd-009', name: '王思远', studentNo: 'S2026-000021', phone: '13612347702',
    collegeId: 'col-02', majorId: 'maj-05', classId: '',
    collegeName: '智能制造学院', majorName: '机电一体化技术', className: '机电2301',
    stageLabel: '学业过程', statusLabel: '两门课程学业预警', tone: 'warning', riskLevel: 'MEDIUM',
    lastEvent: '06-29 帮扶导师首次面谈', metricKeys: ['ACADEMIC', 'RISK']
  },
  {
    id: 'dd-010', name: '李佳琪', studentNo: 'S2026-000022', phone: '15812340566',
    collegeId: 'col-02', majorId: 'maj-05', classId: '',
    collegeName: '智能制造学院', majorName: '机电一体化技术', className: '机电2302',
    stageLabel: '学业过程', statusLabel: '补考待安排', tone: 'warning', riskLevel: 'NONE',
    lastEvent: '06-24 补考报名已确认', metricKeys: ['ACADEMIC']
  },
  {
    id: 'dd-011', name: '张浩宇', studentNo: 'S2027-000108', phone: '13912344310',
    collegeId: 'col-03', majorId: 'maj-06', classId: '',
    collegeName: '商贸管理学院', majorName: '电子商务', className: '电商2401',
    stageLabel: '在校服务', statusLabel: '工单超时申诉处理中', tone: 'warning', riskLevel: 'LOW',
    lastEvent: '07-01 宿舍报修工单升级', metricKeys: ['SERVICE', 'RISK']
  },
  {
    id: 'dd-012', name: '刘欣然', studentNo: 'S2027-000112', phone: '18712340923',
    collegeId: 'col-03', majorId: 'maj-06', classId: '',
    collegeName: '商贸管理学院', majorName: '电子商务', className: '电商2402',
    stageLabel: '在校服务', statusLabel: '服务记录正常', tone: 'success', riskLevel: 'NONE',
    lastEvent: '06-30 完成宿舍调换确认', metricKeys: ['SERVICE']
  },
  {
    id: 'dd-013', name: '黄志强', studentNo: 'S2028-000031', phone: '13112345508',
    collegeId: 'col-04', majorId: '', classId: '',
    collegeName: '建筑工程学院', majorName: '建筑工程技术', className: '建工2501',
    stageLabel: '迎新报到', statusLabel: '未报到 · 辅导员跟进中', tone: 'danger', riskLevel: 'MEDIUM',
    lastEvent: '06-27 电话确认延期报到', metricKeys: ['ORIENTATION', 'RISK']
  },
  {
    id: 'dd-014', name: '杨梦洁', studentNo: 'S2028-000045', phone: '15212341176',
    collegeId: 'col-04', majorId: '', classId: '',
    collegeName: '建筑工程学院', majorName: '建筑工程技术', className: '建工2502',
    stageLabel: '迎新报到', statusLabel: '绿色通道已办理', tone: 'success', riskLevel: 'NONE',
    lastEvent: '06-26 学费缓缴审批通过', metricKeys: ['ORIENTATION']
  }
]

/** 专题报表列表 */
export const reportList = [
  {
    id: 'rpt-001', name: '2026 届毕业生去向落实率专题',
    category: 'EMPLOYMENT', categoryLabel: '就业质量',
    cycle: 'MONTHLY', cycleLabel: '月度',
    scopeName: '全校', ownerName: '方远', updatedAt: '2026-07-01 08:30',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    metricCount: 5, description: '按学院 / 专业拆解去向落实率，对齐教育主管部门报送口径'
  },
  {
    id: 'rpt-002', name: '岗位实习过程质量月报',
    category: 'INTERNSHIP', categoryLabel: '实习过程',
    cycle: 'MONTHLY', cycleLabel: '月度',
    scopeName: '全校', ownerName: '方远', updatedAt: '2026-07-01 08:30',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    metricCount: 6, description: '在岗率、打卡合规率、周报提交率与实习风险的月度过程质量分析'
  },
  {
    id: 'rpt-003', name: '学业预警与帮扶成效分析',
    category: 'ACADEMIC', categoryLabel: '教学质量',
    cycle: 'QUARTERLY', cycleLabel: '季度',
    scopeName: '全校', ownerName: '方远', updatedAt: '2026-07-02 21:40',
    status: 'DRAFT', statusLabel: '草稿', statusTone: 'default',
    metricCount: 4, description: '学业预警触发、帮扶介入与结案成效的闭环分析（配置中）'
  },
  {
    id: 'rpt-004', name: '迎新报到率三年同期对比',
    category: 'SERVICE', categoryLabel: '校园服务',
    cycle: 'ONCE', cycleLabel: '一次性',
    scopeName: '全校', ownerName: '陈立群', updatedAt: '2026-06-20 14:10',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    metricCount: 3, description: '2023-2025 三个年度迎新报到率与绿色通道办理量对比'
  },
  {
    id: 'rpt-005', name: '风险预警处置效率专题',
    category: 'RISK', categoryLabel: '风险治理',
    cycle: 'QUARTERLY', cycleLabel: '季度',
    scopeName: '全校', ownerName: '方远', updatedAt: '2026-04-08 09:00',
    status: 'ARCHIVED', statusLabel: '已归档', statusTone: 'info',
    metricCount: 4, description: '一季度风险预警平均响应时长与逾期升级情况（已归档）'
  },
  {
    id: 'rpt-006', name: '在校服务工单质量分析（旧口径）',
    category: 'SERVICE', categoryLabel: '校园服务',
    cycle: 'MONTHLY', cycleLabel: '月度',
    scopeName: '全校', ownerName: '陈立群', updatedAt: '2026-06-30 11:20',
    status: 'VOIDED', statusLabel: '已作废', statusTone: 'danger',
    metricCount: 3, description: '旧版工单口径月报，已被新口径报表替代',
    voidReason: '服务工单统计口径已升级，旧口径报表停止更新'
  }
]

/** 报表详情（按 id 索引） */
export const reportDetailMap = {
  'rpt-001': {
    id: 'rpt-001', name: '2026 届毕业生去向落实率专题',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    description: '按学院 / 专业拆解 2026 届去向落实率，含签约 / 升学 / 参军 / 创业结构，口径对齐教育主管部门年报要求。',
    config: {
      reportNo: 'RPT-EMP-2026-001', cycleLabel: '月度（每月 1 日 08:30 自动汇聚）',
      caliberLabel: '自然口径（对外报送）', scopeName: '全校 · 2026 届',
      ownerName: '方远', createdAt: '2026-02-05 10:20', updatedAt: '2026-07-01 08:30',
      shareScope: '校级领导 / 就业处 / 各学院管理员', metricCount: 5
    },
    metrics: [
      { id: 'm-01', name: '去向落实率', caliberLabel: '自然口径', value: '69.3', unit: '%', mom: '+6.0pp', momQuality: 'good', yoy: '+3.8pp', yoyQuality: 'good' },
      { id: 'm-02', name: '签约就业人数', caliberLabel: '在册口径', value: '862', unit: '人', mom: '+118', momQuality: 'good', yoy: '+64', yoyQuality: 'good' },
      { id: 'm-03', name: '升学人数', caliberLabel: '在册口径', value: '203', unit: '人', mom: '+9', momQuality: 'good', yoy: '+31', yoyQuality: 'good' },
      { id: 'm-04', name: '待落实人数', caliberLabel: '在册口径', value: '473', unit: '人', mom: '-97', momQuality: 'good', yoy: '-52', yoyQuality: 'good' },
      { id: 'm-05', name: '专业对口率', caliberLabel: '抽样口径', value: '81.4', unit: '%', mom: '+0.6pp', momQuality: 'good', yoy: '-1.2pp', yoyQuality: 'bad' }
    ],
    trend: {
      label: '去向落实率（自然口径）', unit: '%',
      months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
      values: [40.3, 47.5, 54.2, 60.6, 65.1, 69.3]
    }
  },
  'rpt-002': {
    id: 'rpt-002', name: '岗位实习过程质量月报',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    description: '覆盖 2026 届春季实习批次全过程指标，异常与风险数据与岗位实习中心实时同源。',
    config: {
      reportNo: 'RPT-INT-2026-002', cycleLabel: '月度（每月 1 日 08:30 自动汇聚）',
      caliberLabel: '在册口径', scopeName: '全校 · 2026 届春季实习批次',
      ownerName: '方远', createdAt: '2026-03-02 09:00', updatedAt: '2026-07-01 08:30',
      shareScope: '校级领导 / 教务处 / 各学院管理员', metricCount: 6
    },
    metrics: [
      { id: 'm-01', name: '实习在岗率', caliberLabel: '在册口径', value: '92.6', unit: '%', mom: '-1.1pp', momQuality: 'bad', yoy: '+2.3pp', yoyQuality: 'good' },
      { id: 'm-02', name: '打卡合规率', caliberLabel: '在册口径', value: '94.8', unit: '%', mom: '-0.7pp', momQuality: 'bad', yoy: '+1.5pp', yoyQuality: 'good' },
      { id: 'm-03', name: '周报按时提交率', caliberLabel: '在册口径', value: '88.9', unit: '%', mom: '+1.8pp', momQuality: 'good', yoy: '+4.2pp', yoyQuality: 'good' },
      { id: 'm-04', name: '实习协议齐备率', caliberLabel: '在册口径', value: '99.2', unit: '%', mom: '+0.1pp', momQuality: 'good', yoy: '+0.8pp', yoyQuality: 'good' },
      { id: 'm-05', name: '实习风险学生', caliberLabel: '在册口径', value: '34', unit: '人', mom: '+5', momQuality: 'bad', yoy: '-6', yoyQuality: 'good' },
      { id: 'm-06', name: '企业导师评价均分', caliberLabel: '抽样口径', value: '4.4', unit: '分', mom: '+0.1', momQuality: 'good', yoy: '+0.2', yoyQuality: 'good' }
    ],
    trend: {
      label: '实习在岗人数', unit: '人',
      months: ['2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07'],
      values: [1180, 1224, 1246, 1231, 1268, 1259]
    }
  },
  'rpt-003': {
    id: 'rpt-003', name: '学业预警与帮扶成效分析',
    status: 'DRAFT', statusLabel: '草稿', statusTone: 'default',
    description: '草稿报表：指标配置完成后按季度自动汇聚，发布前仅创建人与系统管理员可见。',
    config: {
      reportNo: 'RPT-ACA-2026-003', cycleLabel: '季度（发布后生效）',
      caliberLabel: '在册口径', scopeName: '全校在校生',
      ownerName: '方远', createdAt: '2026-07-02 21:40', updatedAt: '2026-07-02 21:40',
      shareScope: '校级领导 / 教务处', metricCount: 4
    },
    metrics: [],
    trend: null
  },
  'rpt-004': {
    id: 'rpt-004', name: '迎新报到率三年同期对比',
    status: 'PUBLISHED', statusLabel: '已发布', statusTone: 'success',
    description: '2023-2025 三个年度迎新关键指标对比，用于迎新资源投放决策复盘。',
    config: {
      reportNo: 'RPT-SRV-2026-004', cycleLabel: '一次性（数据已冻结）',
      caliberLabel: '自然口径', scopeName: '全校 · 近三个迎新年度',
      ownerName: '陈立群', createdAt: '2026-06-18 16:40', updatedAt: '2026-06-20 14:10',
      shareScope: '校级领导 / 学生处', metricCount: 3
    },
    metrics: [
      { id: 'm-01', name: '2025 级报到率', caliberLabel: '自然口径', value: '96.6', unit: '%', mom: '—', momQuality: 'neutral', yoy: '+0.9pp', yoyQuality: 'good' },
      { id: 'm-02', name: '2024 级报到率', caliberLabel: '自然口径', value: '95.7', unit: '%', mom: '—', momQuality: 'neutral', yoy: '+1.1pp', yoyQuality: 'good' },
      { id: 'm-03', name: '2023 级报到率', caliberLabel: '自然口径', value: '94.6', unit: '%', mom: '—', momQuality: 'neutral', yoy: '-0.4pp', yoyQuality: 'bad' }
    ],
    trend: {
      label: '迎新报到率（按年度）', unit: '%',
      months: ['2021 级', '2022 级', '2023 级', '2024 级', '2025 级', '2026 级(预测)'],
      values: [93.8, 95.0, 94.6, 95.7, 96.6, 96.9]
    }
  },
  'rpt-005': {
    id: 'rpt-005', name: '风险预警处置效率专题',
    status: 'ARCHIVED', statusLabel: '已归档', statusTone: 'info',
    description: '一季度风险处置效率复盘，已归档为只读，历史数据可查不可修改。',
    config: {
      reportNo: 'RPT-RSK-2026-005', cycleLabel: '季度（已归档）',
      caliberLabel: '在册口径', scopeName: '全校 · 2026 年一季度',
      ownerName: '方远', createdAt: '2026-01-06 09:30', updatedAt: '2026-04-08 09:00',
      shareScope: '校级领导 / 各学院管理员', metricCount: 4
    },
    metrics: [
      { id: 'm-01', name: '平均响应时长', caliberLabel: '在册口径', value: '9.6', unit: '小时', mom: '-2.1', momQuality: 'good', yoy: '-4.8', yoyQuality: 'good' },
      { id: 'm-02', name: '72 小时办结率', caliberLabel: '在册口径', value: '86.4', unit: '%', mom: '+3.2pp', momQuality: 'good', yoy: '+7.5pp', yoyQuality: 'good' },
      { id: 'm-03', name: '逾期升级预警', caliberLabel: '在册口径', value: '11', unit: '条', mom: '-4', momQuality: 'good', yoy: '-9', yoyQuality: 'good' },
      { id: 'm-04', name: '重复触发率', caliberLabel: '在册口径', value: '6.8', unit: '%', mom: '-0.9pp', momQuality: 'good', yoy: '-2.2pp', yoyQuality: 'good' }
    ],
    trend: {
      label: '风险预警总量（一季度周度）', unit: '条',
      months: ['W1', 'W3', 'W5', 'W7', 'W9', 'W11'],
      values: [72, 78, 83, 86, 90, 94]
    }
  },
  'rpt-006': {
    id: 'rpt-006', name: '在校服务工单质量分析（旧口径）',
    status: 'VOIDED', statusLabel: '已作废', statusTone: 'danger',
    description: '旧版工单口径月报，已被新口径报表替代；作废记录永久留痕，历史数据只读。',
    config: {
      reportNo: 'RPT-SRV-2025-006', cycleLabel: '月度（已停止更新）',
      caliberLabel: '旧版工单口径', scopeName: '全校',
      ownerName: '陈立群', createdAt: '2025-09-01 10:00', updatedAt: '2026-06-30 11:20',
      shareScope: '学生处', metricCount: 3
    },
    voidInfo: { reason: '服务工单统计口径已升级，旧口径报表停止更新', by: '方远 · 系统管理员', time: '2026-06-30 11:20' },
    metrics: [
      { id: 'm-01', name: '工单按时办结率（旧口径）', caliberLabel: '旧版口径', value: '95.8', unit: '%', mom: '—', momQuality: 'neutral', yoy: '—', yoyQuality: 'neutral' },
      { id: 'm-02', name: '月均工单量（旧口径）', caliberLabel: '旧版口径', value: '742', unit: '件', mom: '—', momQuality: 'neutral', yoy: '—', yoyQuality: 'neutral' },
      { id: 'm-03', name: '满意度（旧口径）', caliberLabel: '旧版口径', value: '4.5', unit: '分', mom: '—', momQuality: 'neutral', yoy: '—', yoyQuality: 'neutral' }
    ],
    trend: null
  }
}

/** 审计日志（新记录由写操作 unshift 到队首） */
export const auditLogs = [
  {
    id: 'al-001', time: '07-03 09:12', userName: '沈国华', roleName: '校级领导',
    action: '导出全校概览', target: '全校概览数据（在册口径）', targetId: '',
    detail: '用途：向上级汇报 · 已脱敏 + 追踪水印（任务 EXP-2026-1198）'
  },
  {
    id: 'al-002', time: '07-02 21:40', userName: '方远', roleName: '系统管理员',
    action: '新增报表配置', target: '学业预警与帮扶成效分析', targetId: 'rpt-003',
    detail: '统计周期：季度 · 共享范围：校级领导 / 教务处'
  },
  {
    id: 'al-003', time: '07-02 16:22', userName: '陈立群', roleName: '学院管理员',
    action: '导出排行分析数据', target: '排行分析数据（信息工程学院）', targetId: '',
    detail: '用途：校内分析 · 已脱敏 + 追踪水印（任务 EXP-2026-1187）'
  },
  {
    id: 'al-004', time: '07-01 15:48', userName: '苏婉晴', roleName: '教务老师',
    action: '查看下钻学生清单', target: '学业过程 · 重点关注学生', targetId: '',
    detail: '查看字段默认脱敏，本次查询已留痕'
  },
  {
    id: 'al-005', time: '07-01 10:05', userName: '沈国华', roleName: '校级领导',
    action: '导出报表数据', target: '2026 届毕业生去向落实率专题', targetId: 'rpt-001',
    detail: '用途：教育主管部门报送 · 已脱敏 + 追踪水印（任务 EXP-2026-1181）'
  },
  {
    id: 'al-006', time: '06-30 11:20', userName: '方远', roleName: '系统管理员',
    action: '作废报表', target: '在校服务工单质量分析（旧口径）', targetId: 'rpt-006',
    detail: '作废原因：服务工单统计口径已升级，旧口径报表停止更新'
  }
]
