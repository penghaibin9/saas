export const WALL_STATUS_TEXT = Object.freeze({
  OK: '可用', ERROR: '暂不可用', MISSING: '字段待接入', RESTRICTED: '无访问权限',
  NO_SCOPE: '未配置范围', LOADING: '加载中', EMPTY: '暂无记录', INVALID: '口径需核查', STALE: '数据已过期'
})

export const WALL_ROUTES = Object.freeze({
  student: { path: '/admin/student/list', permission: 'studentAffairs.student.view' },
  classes: { path: '/admin/campus-service/classes', permission: 'studentAffairs.class.view' },
  leave: { path: '/admin/student-affairs/leave', permission: 'studentAffairs.leave.view' },
  overdue: { path: '/admin/student-affairs/leave/ledger?status=OVERDUE', permission: 'studentAffairs.leave.view' },
  leaveStats: { path: '/admin/student-affairs/leave/stats', permission: 'studentAffairs.leave.view' },
  risk: { path: '/admin/student-affairs/risk', permission: 'studentAffairs.risk.view' },
  riskOpen: { path: '/admin/student-affairs/risk?status=OPEN', permission: 'studentAffairs.risk.view' },
  dorm: { path: '/admin/student-affairs/dorm/stats', permission: 'studentAffairs.dorm.view' },
  aid: { path: '/admin/student-affairs/aid/stats', permission: 'studentAffairs.stats.view' },
  aidReview: { path: '/admin/student-affairs/aid?status=REVIEW', permission: 'studentAffairs.aid.view' },
  funding: { path: '/admin/student-affairs/funding/stats', permission: 'studentAffairs.stats.view' },
  fundingReview: { path: '/admin/student-affairs/funding?status=REVIEW', permission: 'studentAffairs.funding.view' },
  discipline: { path: '/admin/student-affairs/discipline/stats', permission: 'studentAffairs.stats.view' },
  disciplineReview: { path: '/admin/student-affairs/discipline?status=REVIEW', permission: 'studentAffairs.discipline.view' },
  work: { path: '/admin/student-affairs/funding/work-study', permission: 'studentAffairs.funding.view' },
  activity: { path: '/admin/student-affairs/activity/stats', permission: 'studentAffairs.stats.view' },
  talk: { path: '/admin/student-affairs/talk/stats', permission: 'studentAffairs.stats.view' },
  family: { path: '/admin/student-affairs/family', permission: 'studentAffairs.homeSchool.view' },
  archive: { path: '/admin/student-affairs/archive', permission: 'studentAffairs.archive.view' }
})

const summary = (id, label, unit, field, route, note) => ({ id, label, unit, source: 'dashboard', field, route, note })
const domain = (id, label, unit, key, field, route, note) => ({ id, label, unit, source: 'cockpit', key, field, route, note })

export const WALL_METRICS = Object.freeze([
  summary('students', '学生主档数', '人', 'studentTotal', 'student', '当前授权范围内未删除学生主档，不代表实时在校人数'),
  summary('classes', '班级数', '个', 'classTotal', 'classes', '当前授权范围内未删除班级'),
  summary('pendingLeave', '待审请假', '件', 'pendingLeave', 'leave', '辅导员、学院或学工处当前待审核记录'),
  summary('overdueLeave', '逾期未销假', '件', 'overdueLeave', 'overdue', '销假流程逾期，不代表学生实时未归'),
  summary('riskStudents', '未结风险学生', '人', 'riskStudents', 'riskOpen', '按学生去重，不与风险记录数相加'),
  summary('pendingAid', '困难认定在办', '件', 'pendingAid', 'aidReview', '审核与公示中的申请记录'),
  summary('pendingFunding', '奖助评审在办', '件', 'pendingFunding', 'fundingReview', '审核与公示中的申请记录'),
  summary('pendingDiscipline', '处分审理在办', '件', 'pendingDiscipline', 'disciplineReview', '在审及解除审核中的处分记录'),
  domain('riskTotal', '风险记录总量', '条', 'risk', 'total', 'risk', '当前范围风险记录存量，包括已关闭记录'),
  domain('riskOpen', '未关闭风险', '条', 'risk', 'open', 'riskOpen', '状态未关闭的风险记录数'),
  domain('riskHigh', '高危 / 危急记录', '条', 'risk', 'highCritical', 'risk', '风险记录数，不等于高危学生人数'),
  domain('riskLate', '处置超时', '条', 'risk', 'overdue', 'risk', '按后端现行处置时限计算'),
  domain('riskUnassigned', '未分派记录', '条', 'risk', 'unassigned', 'risk', '责任人为空的风险记录'),
  domain('beds', '总床位', '床', 'dorm', 'totalBeds', 'dorm', '当前宿舍资源范围的床位总量'),
  domain('occupied', '已入住床位', '床', 'dorm', 'occupiedBeds', 'dorm', '床位台账占用状态，不是实时在寝人数'),
  domain('vacant', '空床位', '床', 'dorm', 'vacantBeds', 'dorm', '床位台账空闲状态'),
  domain('locked', '锁定床位', '床', 'dorm', 'lockedBeds', 'dorm', '锁定床位不等于待分配床位'),
  domain('aidApproved', '已认定申请', '件', 'aid', 'approved', 'aid', '按申请记录统计，不是去重学生人数'),
  domain('aidTotal', '困难认定申请', '件', 'aid', 'total', 'aid', '当前范围困难认定申请总量'),
  domain('fundingGranted', '已获资助申请', '件', 'funding', 'granted', 'funding', '表示申请获批，不表示银行到账'),
  domain('fundingTotal', '奖助申请总量', '件', 'funding', 'total', 'funding', '当前范围奖助申请总量'),
  domain('workPending', '勤工助学待审', '件', 'workStudy', 'pending', 'work', '申请状态为待审核的记录'),
  domain('workOnboard', '勤工在岗', '条', 'workStudy', 'onboard', 'work', '当前在岗的勤工助学记录'),
  domain('activities', '学生活动', '场', 'activity', 'totalActivities', 'activity', '当前授权范围活动存量'),
  domain('creditStudents', '获二课学分学生', '人', 'activity', 'creditStudents', 'activity', '按学生去重，不是活动参与人次'),
  domain('talks', '谈心谈话记录', '条', 'talk', 'total', 'talk', '已登记谈话记录，不直接表示工作成效'),
  domain('talkCompleted', '已谈话记录', '条', 'talk', 'completed', 'talk', '已完成状态的谈话记录'),
  domain('family', '家校联系记录', '条', 'family', 'total', 'family', '按联系记录统计，不表示家长覆盖人数'),
  domain('familyPending', '家校待回执', '条', 'family', 'pendingReceipt', 'family', '待反馈回执的家校联系记录'),
  domain('archivePending', '待归档档案包', '份', 'archive', 'pending', 'archive', '状态尚未归档的档案包'),
  domain('archiveTotal', '档案包总量', '份', 'archive', 'total', 'archive', '当前授权学生范围内的档案包'),
  domain('leavePendingLate', '请假审批超时', '件', 'leave', 'pendingApprovalOverdue', 'leave', '待审请假中的超时子集'),
  domain('leaveWaitCancel', '待销假', '件', 'leave', 'waitCancel', 'leave', '待学生或教师完成销假确认'),
  domain('leaveClosed', '已销假', '件', 'leave', 'closed', 'leaveStats', '状态已关闭的请假记录'),
  domain('leavePending', '待审批', '件', 'leave', 'pendingReview', 'leave', '请假流程当前待审核记录'),
  domain('leaveOverdue', '逾期未销', '件', 'leave', 'overdue', 'overdue', '请假流程逾期记录')
])

export const metricDefinition = (id) => WALL_METRICS.find(item => item.id === id)
