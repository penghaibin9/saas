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

/**
 * 教务中心 · 便捷提示词 L1（来源：docs 外部制度材料整理，见配置方案 §一 §五——教育部41号令、
 * 江苏大学/东北财经/厦门南洋职院调停课规定、人大/南大/大连理工/河北经贸成绩更正流程、
 * 山东农大/池州学院学籍异动流程、人大/清华/西北大学缓考办法、广西大学/西电学业预警办法等）。
 * 词条为真实制度文件表述整理，非编造；【】为占位符。
 */
const AA_SCHEDCHG_REASON = [
  '因公出差参加【会议/活动名称】，时间与本课程冲突（已附会议通知）。',
  '因病无法授课（已附医院证明），申请调课/停课。',
  '参加【竞赛/评审/监考】等校内公务，与本课程时间冲突。',
  '教学进度调整：本班【实训/考试/实践周】占用原时段，需整体后移。',
  '教室设备故障/教室临时被征用，申请更换时间地点。',
  '承担【学校/学院】统一安排的【招生/评估/培训】工作。'
]
const AA_SCHEDCHG_MAKEUP = [
  '第【N】周星期【X】第【节次】节，在【教室】补授本次课程内容，已通知全体学生。',
  '与学生协商一致，利用第【N】周【自习/晚间】时段集中补课，教室已申请。',
  '本次内容并入第【N】周课程连堂讲授，教学进度不受影响。',
  '改为线上直播补课：【日期 时间】，平台【名称】，录播同步供回看。'
]
const AA_SCHEDCHG_REJECT = [
  '证明材料缺失：因病请附医院证明，因公请附会议通知/公函，补充后重新提交。',
  '未按规定提前【3】天申请，临时调课请先经学院教学负责人电话确认。',
  '停课申请未填写补课安排，请补充补课周次、节次与教室后重报。',
  '目标时段与【班级课表/教室占用/教师监考】冲突，请另选时间。',
  '本课程本学期调课已达【N】次上限，原则上不再受理，特殊情况请附学院意见。'
]
const AA_SCHEDCHG_CANCEL = ['撤销：原冲突事项已取消，恢复按原课表上课，学生已另行通知。']

const AA_GRADE_CHANGE = [
  '登分错误：试卷实际得分【X】分，录入时误登为【Y】分（附试卷复印件）。',
  '合分错误：各题得分合计有误，复核后总分应为【X】分（附试卷复印件）。',
  '批阅疏漏：第【N】题漏批/错批，复核后该题得分【X】分（附试卷及评分标准）。',
  '平时成绩计算错误：按计分规则复算后平时分应为【X】分（附平时成绩计分说明）。',
  '缓考/补考成绩补录：学生已参加【批次】考试，成绩为【X】分。',
  '违纪认定撤销：原旷考/违纪标记经复核撤销，恢复实际成绩。'
]
const AA_GRADE_CHANGE_REVIEW = [
  '已核对试卷与成绩单，更正理由充分、材料齐全，同意更正。',
  '材料不全：请附试卷复印件及详细更改说明（缺一不可），退回补充。',
  '申请理由不充分，不予通过；如有异议请按成绩复核程序办理。',
  '成绩分布异常（不及格率【X】%/优秀率【X】%），请任课教师提交试卷分析后再审。'
]
const AA_GRADE_RETURN = [
  '缺考名单与考务记录不符，请核对旷考/缓考标记后重新提交。',
  '特殊成绩标记（旷考/作弊/违纪）缺认定材料，请补充后重报。',
  '成绩提交超过规定时限，请说明原因并经学院教学负责人签署意见。'
]

const AA_STATUSCHG_GROUPS = {
  SUSPEND: [
    '因病需长期治疗休养（附二级甲等以上医院诊断证明），申请休学【一学年】。',
    '应征入伍（附入伍通知书），申请保留学籍至退役后【2】年内。',
    '参加创新创业实践（附项目证明），按学校规定申请弹性学制休学。'
  ],
  RESUME: ['休学期满，恢复情况良好（因病休学附二甲以上医院康复证明），申请于【学期】复学。'],
  TRANSFER_MAJOR: ['对【目标专业】有浓厚兴趣且符合接收条件，现专业学习确有困难，申请转入。'],
  WITHDRAW: ['因个人发展规划调整，经与家长充分沟通，自愿申请退学。'],
  RETAIN: ['因【学分未修满/毕业设计未完成】，申请延长学习年限【一年】。']
}
const AA_STATUSCHG_OPINION = [
  '情况属实，材料齐全，符合《学籍管理规定》相关条款，同意办理。',
  '经学院党政联席会议研究，同意该生异动，报教务处审批。',
  '已与学生本人及家长确认，知情同意书已签署，同意上报。',
  '材料不全：请补充【医院证明/家长意见/部队通知书】后重新提交。',
  '不符合转专业接收/复学条件（【原因】），不予同意，已告知学生本人。'
]

const AA_WARNING_FOLLOW = [
  '已约谈学生，分析预警课程失分原因为【原因】，共同制定学习计划，每两周复查进度。',
  '已安排学业帮扶结对（帮扶人【姓名】），重点辅导【课程】，周期至学期末。',
  '已电话告知家长预警情况，家长知情并表示配合督促。',
  '学生本学期已重修/补考【课程】，目前出勤与作业情况明显好转。',
  '学生存在心理/经济/健康方面困难，已转介学工（谈心谈话/资助/心理）协同帮扶。'
]
const AA_WARNING_ESCALATE = ['连续两次跟进无改善，本学期新增不及格【N】门，风险加剧，需学院教务牵头处置。']
const AA_WARNING_CLOSE = [
  '补考/重修通过，学分已补齐，绩点回升至【X】，预警解除。',
  '本学期各科目成绩正常，出勤稳定，经确认解除预警。'
]
const AA_WARNING_VOID = ['数据同步错误/规则误命中（【说明】），实际学业状态正常，作废本条。']

const AA_REG_FAIL = [
  '学费未缴清且未办理绿色通道/缓缴手续，暂不予注册。',
  '报到材料不全（缺录取通知书/身份证/档案），限期补交。',
  '入学资格复查存疑（【项目】待核实），暂缓注册待复查结论。'
]
const AA_REG_DEFER = [
  '家庭经济困难，已通过绿色通道申请缓缴学费，先行注册待资助落实。',
  '因病暂不能到校（附医院证明），申请暂缓注册至【日期】。',
  '应征入伍体检/政审期间，暂缓办理，结果确定后按学籍规定处理。'
]

const AA_MAKEUP_REASON = [
  '因病无法参加考试（附二甲以上医院或校医院证明，证明覆盖考试时间），申请缓考。',
  '两门考试时间冲突（【课程A】与【课程B】），申请其中一门缓考。',
  '直系亲属病危/丧事，需紧急返家（附相关证明），申请缓考。',
  '代表学校参加【竞赛/演出/比赛】（附学校公函），与考试时间冲突。',
  '已通过【等级证书/先修课程】，按规定申请免修（附证书复印件）。'
]
const AA_MAKEUP_REVIEW = [
  '医院证明未覆盖考试时间/非二甲以上医院出具，退回补充有效证明。',
  '申请时间晚于考试时间且无突发情况证明，按缺考处理，不予受理。',
  '材料不全：请补交证明材料后重新提交。',
  '不符合免修条件（该课程为实践类/思政类必修，按规定不可免修）。'
]

const AA_TASK_RETURN = [
  '教师本学期工作量已超限（【X】学时），需重新分配任课教师。',
  '任课资格不符：该课程要求【职称/专业】条件，请更换教师。',
  '教学班人数/合班安排有误，请核对后重新下达。'
]
const AA_TASK_REJECT = [
  '与本人其他课表时间冲突（【课程/时段】），请调整时段或另行安排。',
  '本学期已承担【N】门课程，工作量饱和，无法再接新任务。',
  '该课程与本人专业方向不符，建议安排【方向】教师承担。'
]

const AA_REVIEW_RETURN = [
  '学分结构不符：总学分/实践学分比例与专业教学标准不符，请调整后重报。',
  '先修关系错误：【课程A】应先于【课程B】开设，请核对课程序列。',
  '课程信息不完整：缺学时分配/考核方式/教材信息，补齐后重新提交。',
  '与上一版方案差异较大，请附修订说明及专业建设委员会审议意见。'
]

const AA_VOID = [
  '重复建档：与学号【X】记录重复，保留原记录，本条作废。',
  '录入错误：批次/学生信息登错，已在正确批次重新登记。',
  '学籍异动：学生已转专业/退学，本条台账随异动作废。',
  '批次重复导入，作废本批冗余数据。'
]

const AA_EXPORT_PURPOSE = [
  '期末教学质量分析会议材料',
  '本科教学工作合格评估/审核评估支撑材料',
  '上级教育主管部门检查报送',
  '学院教学工作例会数据通报'
]

const AA_REMARK = [
  '教室备注：多媒体设备【型号】；合班教室，容量【N】；维修中，预计【日期】恢复。',
  '合并说明：小班合并授课 / 同一教师同一课程跨班合并。'
]
const AA_TEXTBOOK_REDUCE = [
  '家庭经济困难学生按资助政策减免教材费。',
  '教材循环使用，本学期免征订费用。'
]
const AA_ARCHIVE_UNFREEZE = ['审计/复查需要，经学校管理员批准，限期【日期】前重新冻结。']
const AA_CLASSROOM_REJECT = ['该时段已有教学安排，教学用途优先，请改约【时段】。']

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
  'sa.class.material': CLASS_MATERIAL,

  // —— 教务中心（aa.*）——
  'aa.schedchg.reason': AA_SCHEDCHG_REASON,
  'aa.schedchg.makeup': AA_SCHEDCHG_MAKEUP,
  'aa.schedchg.reject': AA_SCHEDCHG_REJECT,
  'aa.schedchg.cancel': AA_SCHEDCHG_CANCEL,
  'aa.grade.change': AA_GRADE_CHANGE,
  'aa.grade.changeReject': AA_GRADE_CHANGE_REVIEW,
  'aa.grade.collegeReview': AA_GRADE_CHANGE_REVIEW,
  'aa.grade.return': AA_GRADE_RETURN,
  'aa.statuschg.reason': { groups: AA_STATUSCHG_GROUPS, all: Object.values(AA_STATUSCHG_GROUPS).flat() },
  'aa.statuschg.opinion': AA_STATUSCHG_OPINION,
  'aa.warning.follow': AA_WARNING_FOLLOW,
  'aa.warning.escalate': AA_WARNING_ESCALATE,
  'aa.warning.close': AA_WARNING_CLOSE,
  'aa.warning.void': AA_WARNING_VOID,
  'aa.reg.fail': AA_REG_FAIL,
  'aa.reg.defer': AA_REG_DEFER,
  'aa.makeup.reason': AA_MAKEUP_REASON,
  'aa.makeup.reject': AA_MAKEUP_REVIEW,
  'aa.makeup.supplement': AA_MAKEUP_REVIEW,
  'aa.task.return': AA_TASK_RETURN,
  'aa.task.reject': AA_TASK_REJECT,
  'aa.review.return': AA_REVIEW_RETURN,
  'aa.void': AA_VOID,
  'common.exportPurpose': AA_EXPORT_PURPOSE,
  'aa.remark': AA_REMARK,
  'aa.textbook.reduce': AA_TEXTBOOK_REDUCE,
  'aa.archive.unfreeze': AA_ARCHIVE_UNFREEZE,
  'aa.classroom.reject': AA_CLASSROOM_REJECT
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
