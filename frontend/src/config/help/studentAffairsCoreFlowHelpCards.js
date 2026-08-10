/** Help Center V3-04 · 学工四条高频办理线。只收编当前代码已经证明的正式事实。 */
export const STUDENT_AFFAIRS_CORE_FLOW_HELP_CARDS = [
  {
    id: 'sa-v3-leave-lifecycle',
    module: '学工中心 · 请假与销假',
    title: '学生请假后怎么审批、续假、销假和处理逾期',
    roles: ['学生', '辅导员', '学院管理员', '学工处管理员'],
    route: '/admin/student-affairs/leave',
    entry: '学工中心 → 请假审批；后续办理在「销假与续假」',
    keywords: ['请假', '续假', '销假', '退回', '驳回', '逾期', 'RETURNED', 'EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', '409'],
    summary: '请假不是“通过/驳回”两态。正式真相列包含 DRAFT、SUBMITTED、辅导员/学院/学工处审批、APPROVED、RETURNED、REJECTED、EXTENSION_REVIEW、WAIT_CANCEL_LEAVE、OVERDUE、CLOSED、ARCHIVED 等状态；请假天数决定审批层级，后续续假和销假继续受状态机、具体待办受理人和版本冲突保护约束。',
    prerequisites: [
      '学生、班级和辅导员责任关系必须可解析；需要审批的节点必须存在具体 assignee，否则服务端以 ASSIGNEE_NOT_CONFIGURED 拒绝。',
      '页面权限 studentAffairs.leave.view 只代表可进入页面；写操作仍由对应端点权限、数据范围、当前节点和待办受理人共同裁决。',
      '审批链按请假时长选择：默认 ≤3 天仅辅导员，>3 且 ≤7 天增加学院，>7 天再增加学工处；当前阈值由服务端单一来源控制。'
    ],
    permissions: [
      '学生仅办理本人申请；辅导员/班主任按 CLASS 范围和本人待办办理，学院按 COLLEGE 范围，学工处/校级角色按 TENANT_ALL 范围。',
      '非 TENANT_ALL 用户即使能看到节点，也不能处理未指派给本人的审批/续假/销假待办。'
    ],
    steps: [
      '学生提交后进入真实审批节点；审批节点只允许 APPROVE / RETURN / REJECT。RETURN 是退回修改，不等于 REJECT 终止。',
      '审批全部通过后进入 APPROVED。此时可发起销假、续假；超过应返时间可进入 OVERDUE，由正式逾期处置动作处理。',
      '续假进入 EXTENSION_REVIEW，只能 APPROVE_EXTENSION / REJECT_EXTENSION；销假申请进入 WAIT_CANCEL_LEAVE，只能 CONFIRM_CANCEL / RETURN_CANCEL。',
      '退回状态 RETURNED 允许 EDIT_RETURNED / RESUBMIT；前端不得在其他状态伪造“重新提交”。',
      '所有关键写操作携带 expectedVersion；别人已经处理后继续用旧版本提交会收到冲突提示，应刷新服务器真值再操作。'
    ],
    successCriteria: ['审批状态、真实 WorkflowTask、UnifiedTodo 和学生端看到的结果一致；退回/驳回不会混淆。', '销假确认后进入 CLOSED；续假、逾期和销假均留业务审计与消息事件。'],
    troubleshooting: ['提示未配置受理人：先修辅导员/学院/学工处责任配置，不能临时绕过 workflow。', '按钮不出现：先看服务器 allowedActions/current status；APPROVED、RETURNED、OVERDUE 的可办动作不同。', '提示版本冲突/409：刷新详情和待办，不重复提交旧页面数据。'],
    nextSteps: ['请假通过后关注是否需要续假/按时销假；超过返校时间进入逾期处置，不把 APPROVED 当流程永久终点。'],
    contactAdminWhen: ['责任关系已配置但服务端仍提示 ASSIGNEE_NOT_CONFIGURED。', '刷新后当前状态、待办受理人和 allowedActions 仍明显不一致。']
  },
  {
    id: 'sa-v3-aid-funding',
    module: '学工中心 · 困难认定与奖助资助',
    title: '困难认定和奖学金/助学金为什么是两条连续但独立的流程',
    roles: ['学生', '辅导员', '学院管理员', '资助老师', '学工处管理员'],
    route: '/admin/student-affairs/aid',
    entry: '先在「困难认定」形成认定事实；再到「奖助勤贷补」办理奖学金/助学金',
    keywords: ['困难认定', '资助', '奖学金', '助学金', '公示', '困难学生库', 'PUBLICITY', 'GRANTED', '敏感家庭经济'],
    summary: '困难认定与资助不是同一状态机。认定经过班级评议、辅导员、学院、学校终审和公示，APPROVED 后写入困难学生库；助学金再把“困难库在库”作为硬资格，奖学金则校验学籍、未解除处分、挂科等权威事实。当前正式启用的资助类型是 SCHOLARSHIP / GRANT。',
    prerequisites: [
      '困难认定家庭经济字段属于敏感数据：列表默认脱敏，income_encrypted 不直接出列表；完整查看必须满足敏感权限与审计条件。',
      '困难认定状态链：CLASS_REVIEW → COUNSELOR_REVIEW → COLLEGE_REVIEW → SCHOOL_REVIEW → PUBLICITY → APPROVED；另有 REJECTED / ADJUST_REVIEW / ARCHIVED。',
      '资助当前正式启用 SCHOLARSHIP / GRANT；勤工、贷款等虽有模型/菜单，不在本 V3 卡中冒充已完成的同等主链。'
    ],
    permissions: [
      '页面分别使用 studentAffairs.aid.view / studentAffairs.funding.view；审批仍受具体 approve/counselorReview 等权限、CLASS/COLLEGE/TENANT_ALL 范围和 WorkflowTask 指派约束。',
      'FUNDING_TEACHER 是窄权限的全校资助经办角色；全校数据范围不等于拥有学工其他领域权限。'
    ],
    steps: [
      '先受理困难认定；班级评议、辅导员初审、学院复审、学校终审按真实节点推进。学校终审通过不等于最终认定，仍进入 PUBLICITY。',
      '公示完成后才进入 APPROVED，并把困难等级事实写入困难学生库；异议、动态调整走各自正式记录，不直接改最终等级。',
      '建立/选择资助项目后受理申请。奖学金服务端重新校验在籍状态、有效处分和成绩事实；助学金重新校验困难学生库。',
      '资助审批按 COUNSELOR_REVIEW → COLLEGE_REVIEW → SCHOOL_REVIEW → PUBLICITY 推进；最终 GRANTED 才是正式获资助事实。',
      '资格校验规则版本和事实快照会被保存；不要通过前端改显示值绕过权威学籍/成绩/处分/困难库。'
    ],
    successCriteria: ['困难认定 APPROVED 与困难学生库事实一致；家庭经济原文不在普通列表泄漏。', '资助 GRANTED 具备真实资格快照、审批/公示轨迹和 360 阶段事件，困难认定与资助记录可分别追溯。'],
    troubleshooting: ['助学金提示不满足资格：先核对困难认定是否已正式 APPROVED 并进入困难库，不把“已提交/公示中”当已认定。', '奖学金被资格拦截：检查在籍、未解除处分、挂科事实，不手工修改资助申请结果。', '能看认定列表但看不到家庭经济原文属于正常最小暴露；只有敏感权限和允许节点才可 reveal。'],
    nextSteps: ['困难认定通过后再进入具体资助项目；资助公示完成并 GRANTED 后进入发放/台账，不把 SCHOOL_REVIEW 通过当已发放。'],
    contactAdminWhen: ['权威学籍/处分/成绩/困难库事实已正确但资格快照仍错误。', '敏感权限与业务节点均满足但 reveal 审计失败或错误返回明文。']
  },
  {
    id: 'sa-v3-discipline',
    module: '学工中心 · 违纪处分',
    title: '处分如何登记、生效、申诉和解除，为什么生效后不能直接编辑',
    roles: ['辅导员', '学院管理员', '学工处管理员', '学校管理员'],
    route: '/admin/student-affairs/discipline',
    entry: '学工中心 → 违纪处分；送达与申诉在「处分送达与申诉」',
    keywords: ['处分', '违纪', '解除', '申诉', 'EFFECTIVE', 'REMOVE_REVIEW', 'REMOVED', 'RETURNED', 'EXPEL'],
    summary: '处分主链是 REGISTERED → COLLEGE_REVIEW → STUDENT_AFFAIRS_REVIEW →（严重处分再 SCHOOL_REVIEW）→ EFFECTIVE。EFFECTIVE 会事务内投影到正式处分台账并进入 360，之后不可普通编辑。解除是独立子流程 EFFECTIVE → REMOVE_REVIEW → REMOVED，历史保留。',
    prerequisites: [
      '处分类型必须是 WARNING / SERIOUS_WARNING / DEMERIT / PROBATION / EXPEL；违纪事实至少 5 字。',
      'PROBATION / EXPEL 属严重处分，需要校级审批；其他处分不应被帮助文档虚构成同一审批层级。',
      '案件必须属于当前用户真实数据范围；学院、学工处、校级节点还有节点角色边界和具体 WorkflowTask 指派。'
    ],
    permissions: [
      '页面使用 studentAffairs.discipline.view；登记、审批、送达、申诉、解除等写操作以端点权限为准。',
      '学院仅办理 COLLEGE_REVIEW；学工处复核、校级审批和解除处终审只允许 TENANT_ALL 级授权角色；普通辅导员不能越级。'
    ],
    steps: [
      '登记事实后状态 REGISTERED；只有 REGISTERED / RETURNED 可提交或在允许条件下撤销，提交后进入 COLLEGE_REVIEW。',
      '学院初审后进入 STUDENT_AFFAIRS_REVIEW；严重处分再进入 SCHOOL_REVIEW。审批通过形成 EFFECTIVE 正式事实。',
      'EFFECTIVE 处分与正式投影台账必须一一对账；生效后禁止直接编辑，纠错必须走正式后续业务而不是改数据库。',
      '处分送达和申诉使用独立记录；申诉状态包含 SUBMITTED / REVIEWING / UPHELD / REVISED / REVOKED，不把申诉提交等同于处分自动撤销。',
      '符合解除条件时发起 REMOVE_REVIEW，经过辅导员、学院、学工处终审后进入 REMOVED；历史处分仍保留。'
    ],
    successCriteria: ['EFFECTIVE 案件数量与 ACTIVE 正式处分投影一致，360 有对应事实。', '解除后正式投影状态同步更新但历史不删除；申诉/送达/解除都有独立审计链。'],
    troubleshooting: ['生效后编辑返回冲突属于保护机制，不要改前端放开按钮。', '当前审批人无权：核对 COLLEGE / TENANT_ALL 范围、当前节点和 WorkflowTask assignee。', '学生申诉后处分仍显示有效：先看申诉最终结果；SUBMITTED/REVIEWING 不会自动撤销正式处分。'],
    nextSteps: ['处分 EFFECTIVE 后完成正式送达并关注申诉；符合解除条件时走 REMOVE_REVIEW，不直接删除历史处分。'],
    contactAdminWhen: ['EFFECTIVE 与正式处分投影数量不一致。', '节点、范围和受理人均正确但仍出现跨节点授权异常。']
  },
  {
    id: 'sa-v3-care-risk',
    module: '学工中心 · 学生关怀与风险',
    title: '谈心谈话、心理关注、家校联系和风险处置如何衔接',
    roles: ['辅导员', '班主任', '心理老师', '学工处管理员', '学校管理员'],
    route: '/admin/student-affairs/talk',
    entry: '日常关怀从「谈心谈话」进入；心理转介在「心理关注」；正式风险在「风险预警」',
    keywords: ['谈心谈话', '重点学生', '心理关注', '家校联系', '风险', 'REFERRED', 'FOLLOWING', 'ESCALATED', 'SENSITIVE_VIEW', 'PSY_STUDENT'],
    summary: '学生关怀不是“谈过就结束”。谈话从 PLANNED/SCHEDULED 记录为 COMPLETED 或 FOLLOW_UP，可继续跟进、办结、转家校或转风险。心理转介是强敏感独立事实：系统不自动诊断，状态 REFERRED → FOLLOWING / ESCALATED → CLOSED；危机升级才创建 source=MENTAL 的 CRITICAL 风险并交给风险中枢继续处置。',
    prerequisites: [
      '谈话至少选择一名真实可访问学生；正式谈话内容不少于 20 字。PSYCHOLOGY 类型正文对未授权角色始终遮蔽。',
      '心理转介事由摘要 5–500 字；回访、危机升级依据、关闭结论均为 5–300 字。',
      '心理逐生范围只认 t_teacher_student_scope.teacher_key 的稳定工号/登录标识；realName / teacher_name 不再作为授权凭证，同名教师不能共享敏感学生范围。'
    ],
    permissions: [
      '普通谈话页面使用 studentAffairs.talk.view 并受 CLASS/COLLEGE/TENANT_ALL 等学工范围约束；心理明细页面使用 studentAffairs.risk.psyDetail.view，但页面权限仍不等于可看任意学生原文。',
      '心理名单按 PSY_STUDENT 逐生授权；列表恒为摘要。查看原文明细还要求允许角色 + 查看原因不少于 5 字 + SENSITIVE_VIEW 安全审计成功；审计故障时 503 fail-closed。'
    ],
    steps: [
      '创建谈话计划后产生每生一条 PLANNED / SCHEDULED 记录；填写真实谈话后进入 COMPLETED，需继续关注则直接进入 FOLLOW_UP。',
      'COMPLETED / FOLLOW_UP 可 FOLLOW、CLOSE、TO_HOME_SCHOOL 或 TO_RISK；转风险会创建 NEW 风险记录，转家校会创建独立联系记录，原谈话仍保留关联 ID。',
      '需要心理专业跟进时登记人工转介 REFERRED；可持续 FOLLOW 进入 FOLLOWING。系统不会根据文本自动诊断或自动升级。',
      '确需危机升级时执行 ESCALATE，生成 source=MENTAL、risk_level=CRITICAL、status=NEW 的正式风险，并把 risk_id 回链到心理转介。',
      '风险进入既有 sa-card-risk-handle 流程继续 ASSIGNED/PROCESSING/FOLLOWING/ESCALATED/CLOSED；心理转介和风险是关联的两个事实，不互相冒充。'
    ],
    successCriteria: ['谈话、家校、心理转介、风险分别留独立记录并通过关联 ID 串联；360 只展示允许的摘要事实。', '心理原文未授权永不泄露；同名老师不会因为姓名相同获得对方 PSY_STUDENT 范围；危机风险由风险中枢正式闭环。'],
    troubleshooting: ['能看到“需关注”但看不到心理正文是正常最小暴露，不是页面故障。', '心理老师/辅导员看不到某生：核对稳定 teacher_key 的 PSY_STUDENT 授权，不通过 realName 补授权。', '敏感查看返回 503：安全审计不可用时系统故意拒绝明文，应修审计链而不是关闭保护。'],
    nextSteps: ['一般关怀可继续跟进/家校/办结；转成正式风险后进入风险处置卡，风险关闭后再按实际情况关闭心理转介。'],
    contactAdminWhen: ['PSY_STUDENT 已用正确 teacher_key 授权但仍看不到目标学生。', '发现任何未填写查看原因、未写安全审计却返回心理原文的情况，应立即按安全缺陷处理。']
  }
]
