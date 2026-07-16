/**
 * 学工中心 · 便捷提示词（快捷用语）库 L1（系统预设，静态数据，零后端改动）。
 * 内容来源：docs 外部制度材料整理（教育部辅导员工作规范 / 上海市高校心理危机干预办法 /
 * 陕西省困难认定实施办法 / 华南农大处分办法 / 高校宿舍检查评分办法等，见配置方案 §一 §五）。
 * 词条为真实公文/工作范文措辞，不得随意改写；【】为占位符，插入后自动选中首个占位符。
 *
 * L2（租户自定义）/ L3（个人常用）留待后续按真实使用率决定是否投入，本文件只做 L1。
 */

const LEAVE_APPROVE = [
  '情况属实，同意请假。离校期间注意安全，保持通讯畅通，按时返校销假。',
  '病假材料齐全，同意。注意休息、及时就医，如需延长请提前办理续假。',
  '同意。请假期间课程请自行与任课教师沟通补课事宜。',
  '事由清楚、家长知情，同意。往返途中注意交通安全。'
]

const LEAVE_RETURN = [
  '病假需提供县级以上医院诊断证明，请补充材料后重新提交。',
  '事假请补充家长知情证明或联系方式，核实后再审批。',
  '请假事由描述不清，请补充具体事由、目的地及紧急联系人。',
  '请假时段与考试/实训冲突，请先按教务规定办理缓考或调整时间后再申请。',
  '请假天数超出本级审批权限，请按流程提交学院/学工处审批。',
  '附件不清晰/无法核验，请重新上传有效证明材料。',
  '续假需说明原因并附新证明材料，原假期临近到期请尽快补充。'
]

const TALK_CONTENT_GROUPS = {
  ACADEMIC: [
    '了解近期学习状态。该生反映【课程】学习吃力，主要困难是【原因】。已建议制定学习计划，并协调学习帮扶/朋辈辅导。',
    '本学期已有【N】门课程预警，与学生分析原因为【原因】，约定每周反馈学习进度。'
  ],
  PSYCHOLOGY: [
    '学生近期情绪【状态】，主要压力来源为【学业/家庭/人际/经济】。已倾听疏导，告知校心理咨询预约渠道，约定保持联系。（注：仅记录行为观察，不写诊断结论）'
  ],
  DAILY: [
    '例行谈话。学生近期学习生活正常，人际关系良好，无特殊困难，对【事项】提出建议。'
  ],
  DISCIPLINE: [
    '就【违纪事项】进行诫勉谈话，重申校规校纪。学生对错误有认识，表示不再违反并接受处理。'
  ],
  AID: [
    '核实家庭经济情况：家庭主要收入为【来源】，近期变故【有/无】。告知可申请的资助项目与流程。'
  ],
  DORM: [
    '就宿舍【卫生/矛盾/安全】问题谈话，了解情况为【情况】，已提出整改要求并约定复查时间。'
  ],
  EMPLOYMENT: [
    '了解求职（实习）进展：已投递【N】份，意向方向【方向】。建议完善简历并关注校园招聘信息。'
  ],
  INTERNSHIP: [
    '了解求职（实习）进展：已投递【N】份，意向方向【方向】。建议完善简历并关注校园招聘信息。'
  ]
}

const TALK_RESULT = [
  '谈话态度良好，认识到位，情况已了解，无需跟进。',
  '情况基本掌握，转持续跟进，两周内回访。',
  '存在风险信号，已转风险处置单跟进。',
  '需家长配合，已转家校联系。',
  '学生承诺【事项】，下次谈话核对落实情况。'
]

const FAMILY_REASON = [
  '反馈近期学业情况（预警课程/出勤）',
  '反馈考勤异常，核实学生去向',
  '沟通家庭经济困难认定与资助政策',
  '告知违纪处理决定并听取家长意见',
  '假期离校/返校安全提醒',
  '反馈学生在校异常表现，请家长协同关注'
]

const FAMILY_RESULT = [
  '家长已知晓上述情况，表示配合学校工作，将督促提醒学生。',
  '与家长约定每周电话沟通一次，互通学生动态。',
  '家长反馈学生在家期间表现正常，无异常情况。',
  '家长表示将来校面谈，时间另约。',
  '电话未接通，已改短信告知，待回复后补充记录。'
]

const DISCIPLINE_FACT = [
  '该生于【日期】在【地点】发生【行为】，经【辅导员/宿管/监考教师】查证属实，违反《学生管理规定》第【X】条。',
  '该生本学期累计旷课【N】学时，经多次提醒未改正，已约谈本人并告知处理依据。',
  '该生在【课程】考试中携带/使用【物品】，被监考教师当场发现，证据已封存。',
  '该生在宿舍使用违规电器【名称】，检查时当场收缴，本人签字确认。',
  '该生【日期】夜不归宿且未履行报备手续，联系本人核实为【去向】。'
]

const COMMON_REJECT = [
  '事实描述不完整（缺时间/地点/证据来源），请补充后重新提交。',
  '证据材料不足，暂不予立案，请补充证人证言或影像记录。',
  '该事项不属于违纪情形，建议按【谈心谈话/宿舍整改】处理。',
  '申报信息与佐证材料不一致，请核对后重新提交。'
]

const REVIEW_OPINION = [
  '经复核申诉材料与原始记录，事实认定清楚、程序合规，维持原处理决定。',
  '申诉理由部分成立：【事项】认定有误，予以更正；其余维持原决定。',
  '提交的新证据改变事实认定，原决定撤销，重新启动认定程序。',
  '复核中需补充核实【材料】，请申诉人于【日期】前补交。'
]

const AID_STATEMENT = [
  '家庭共【N】口人，主要收入来源为【务农/务工/低保】，年收入约【金额】元。因【变故：疾病/灾害/失业/单亲】导致经济困难，现有【低保证/建档立卡/残疾证】等佐证。',
  '父/母因【疾病】长期治疗，医疗支出大，家庭负债【金额】元，难以负担学费及生活费。'
]

const AID_ADJUST = [
  '民主评议结果与申请等级不一致，经评议小组核议调整为【一般/特别】困难。',
  '学生持有建档立卡/低保佐证，按政策直接认定为特别困难。',
  '提供材料与走访了解情况有出入，经核实调整认定等级。',
  '家庭经济状况较上学年好转，等级相应下调。'
]

const AID_REJECT = [
  '家庭收入证明材料不全，请补充【乡镇/街道】出具的证明后重新提交。',
  '申请说明与佐证材料不符，本次不予认定，可补充材料后申请复议。',
  '不符合本批次认定条件（详见学校资助政策），不予受理。',
  '已享受同类资助项目，按规定不可重复申请。'
]

const MENTAL_REFERRAL = [
  '情绪持续低落超过两周，伴睡眠差、缺勤增多，建议专业评估。',
  '谈话中流露消极言语，已启动关注，建议心理中心介入评估。',
  '学生主动求助，自述压力大难以调节，转介校内咨询。'
]

const MENTAL_FOLLOWUP = [
  '本次回访：学生情绪平稳，按约定接受咨询/复诊，家长知情并陪同。',
  '本次回访：学生正常出勤上课，宿舍关系正常，室友反馈无异常。',
  '本次回访：情绪有反复，已加密回访频次，并同步家长与心理中心。'
]

const MENTAL_CLOSE = [
  '经心理中心评估情绪稳定，家长知情，解除重点关注，转日常关注。'
]

const MENTAL_ESCALATE = [
  '出现危机信号（【信号】），立即升级并接入风险处置，已通知家长与学院。'
]

const RISK_HANDLE = [
  '处置：已第一时间联系学生本人，核实其人身安全，情况为【情况】。',
  '处置：已通知家长，家长知情并表示配合，约定【安排】。',
  '处置：已约谈学生并制定帮扶方案：【措施】，责任人【姓名】。'
]

const RISK_FOLLOWUP = ['跟进：本周情况平稳，继续按周跟进。']
const RISK_TRANSFER = ['转办：职责调整，转交【接收人】跟进处理，已交接全部背景信息。']
const RISK_ESCALATE = ['升级：风险等级提升（【原因】），需院系领导关注并统筹处置。']
const RISK_CLOSE = ['关闭：学生情况稳定，连续两周无异常，家长知情，风险解除。']
const RISK_REOPEN = ['重开：风险复发（【表现】），重新启动跟进。']

const DORM_EXCEPTION_GROUPS = {
  HYGIENE: ['卫生不合格：地面垃圾未清理、桌面床铺杂乱、有异味，限 3 日内整改，届时复查。'],
  SAFETY: ['发现安全隐患：私拉电线/堵塞消防通道，已当场要求整改并拍照留存。'],
  CONTRABAND: ['发现违规电器【热得快/电煮锅/大功率设备】，已当场收缴登记，学生签字确认。'],
  NIGHT_ABSENCE: ['查寝时段该生不在寝室，电话【已联系，自述在外住宿未报备/未接通，已升级联系家长】。']
}

const REVEAL_REASON = [
  '办理资助资格复核，需核对家庭经济与联系信息。',
  '处置突发事件，需立即联系学生家长。',
  '家校联系工作需要，拨打家长电话核实情况。',
  '学生本人申请事项办理，需核验身份与联系方式。'
]

const CLASS_MATERIAL = [
  '第【N】周主题班会记录',
  '【月份】安全教育主题活动',
  '班级综合测评民主评议材料',
  '期【中/末】考风考纪教育班会'
]

/** sceneKey → 简单数组，或 { groups, all } 结构（含条件分组置顶场景） */
export const QUICK_PHRASES = {
  'sa.leave.approve': LEAVE_APPROVE,
  'sa.leave.return': LEAVE_RETURN,
  'sa.talk.content': { groups: TALK_CONTENT_GROUPS, all: Object.values(TALK_CONTENT_GROUPS).flat() },
  'sa.talk.result': TALK_RESULT,
  'sa.family.reason': FAMILY_REASON,
  'sa.family.result': FAMILY_RESULT,
  'sa.discipline.fact': DISCIPLINE_FACT,
  'sa.discipline.reject': COMMON_REJECT,
  'common.reject': COMMON_REJECT,
  'common.reviewOpinion': REVIEW_OPINION,
  'sa.aid.statement': AID_STATEMENT,
  'sa.aid.adjust': AID_ADJUST,
  'sa.aid.reject': AID_REJECT,
  'sa.mental.referral': MENTAL_REFERRAL,
  'sa.mental.followup': MENTAL_FOLLOWUP,
  'sa.mental.close': MENTAL_CLOSE,
  'sa.mental.escalate': MENTAL_ESCALATE,
  'sa.risk.handle': RISK_HANDLE,
  'sa.risk.followup': RISK_FOLLOWUP,
  'sa.risk.transfer': RISK_TRANSFER,
  'sa.risk.escalate': RISK_ESCALATE,
  'sa.risk.close': RISK_CLOSE,
  'sa.risk.reopen': RISK_REOPEN,
  'sa.dorm.exception': { groups: DORM_EXCEPTION_GROUPS, all: Object.values(DORM_EXCEPTION_GROUPS).flat() },
  'sa.dorm.reject': COMMON_REJECT,
  'common.revealReason': REVEAL_REASON,
  'sa.class.material': CLASS_MATERIAL
}

/** 取某个 sceneKey 下的词条列表；group 命中时该组置顶，其余分组词条仍追加在后（不是不可见，只是不置顶）。 */
export function getQuickPhrases(sceneKey, group) {
  const entry = QUICK_PHRASES[sceneKey]
  if (!entry) return []
  if (Array.isArray(entry)) return entry
  const g = group && entry.groups[group]
  if (!g) return entry.all
  const rest = entry.all.filter((p) => !g.includes(p))
  return [...g, ...rest]
}
