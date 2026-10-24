export const STUDENT_AFFAIRS_ROLE_GUIDANCE = Object.freeze({
  'sa-v3-leave-lifecycle': [
    { role: '学生', roleCode: 'STUDENT', permission: '本人请假端点', scope: 'SELF，仅本人', relation: '学号必须与本人申请匹配', canDo: '提交、退回后修改重交、按状态发起续假/销假；不能处理他人申请。' },
    { role: '辅导员/班主任', roleCode: 'COUNSELOR / CLASS_ADVISOR', permission: '请假相关权限中实际授予的操作', scope: 'CLASS，限责任班级', relation: '审批/续假/销假待办还必须实际指派给本人', canDo: '办理本人责任范围和本人待办；不能越级代学院/学工处审批。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN / COLLEGE_SA', permission: '对应 leave 审批动作', scope: 'COLLEGE，限授权学院', relation: '仅在流程确实进入“学院审核”时办理', canDo: '办理本学院节点，不跨学院。' },
    { role: '学工处管理员', roleCode: 'STUDENT_AFFAIRS_ADMIN', permission: '对应 leave 审批/管理动作', scope: '全校范围，本校学工范围', relation: '长假进入“学工处审核”等实际环节时办理', canDo: '校级学工收口，但仍不能跳过状态机和版本校验。' }
  ],
  'sa-v3-aid-funding': [
    { role: '学生', roleCode: 'STUDENT', permission: '本人认定/资助端点', scope: 'SELF，仅本人', relation: '本人申请与当前批次/项目资格匹配', canDo: '申请本人困难认定和资助，查看本人结果。' },
    { role: '辅导员', roleCode: 'COUNSELOR', permission: '资助辅导员审核权限，或对应的资助初审操作', scope: 'CLASS', relation: '当前 WorkflowTask 必须落在本人责任学生/本人待办', canDo: '办理本班初审；困难家庭原文只在允许节点按敏感规则查看。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN / COLLEGE_SA', permission: '对应 aid/funding 审批动作', scope: 'COLLEGE', relation: '当前节点必须是学院可见节点', canDo: '办理本院复审，不执行学校终审。' },
    { role: '资助老师', roleCode: 'FUNDING_TEACHER', permission: '窄限 aid/funding/dashboard/student/stats 等资助权限', scope: '全校范围，但仅限资助领域', relation: '仍受认定/项目状态机、资格快照和待办约束', canDo: '全校资助经办；全校数据范围不等于学工全域权限。' }
  ],
  'sa-v3-discipline': [
    { role: '辅导员', roleCode: 'COUNSELOR', permission: '实际授予的 discipline 动作', scope: 'CLASS', relation: '仅办理本人负责的学生和解除流程允许的“辅导员审核”', canDo: '登记/协同及解除初审等被授权动作，不能学工处终审。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN / COLLEGE_SA', permission: '对应 discipline 审批动作', scope: 'COLLEGE', relation: '主流程仅“学院审核”；解除流程按实际的学院环节', canDo: '办理本院处分初审/解除复审。' },
    { role: '学工处/学校管理员', roleCode: 'STUDENT_AFFAIRS_ADMIN / SCHOOL_ADMIN', permission: '对应 discipline review/manage 动作', scope: 'TENANT_ALL', relation: '学工处复核、严重处分校级审批、解除终审仍各自受节点约束', canDo: '校级收口；不能直接编辑已经 EFFECTIVE 的正式处分。' }
  ],
  'sa-v3-care-risk': [
    { role: '辅导员/班主任', roleCode: 'COUNSELOR / CLASS_ADVISOR', permission: '谈话、风险查看等实际权限', scope: '班级范围；查看心理明细另需心理授权', relation: '普通谈话按责任班级；心理学生必须有稳定 teacher_key 逐生授权', canDo: '做日常谈话/跟进/家校/转风险；不能因姓名相同查看别人的心理学生。' },
    { role: '心理老师', roleCode: 'PSYCHOLOGY_TEACHER', permission: '心理明细查看等实际权限', scope: '学生个人范围，仅限已获心理授权的学生', relation: '只认 TeacherStudentScope.teacher_key 的稳定工号/登录标识；原文查看还需原因+安全审计', canDo: '办理授权学生心理转介/回访/危机升级；不能看未点名授权学生。' },
    { role: '学工处管理员', roleCode: 'STUDENT_AFFAIRS_ADMIN', permission: 'talk/risk 等实际权限', scope: 'TENANT_ALL', relation: '默认并不因此获得心理原始明细权限', canDo: '可查看学工风险与普通关怀记录；心理原文继续服从专项敏感权限。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '对应管理/敏感查看权限', scope: 'TENANT_ALL', relation: '查看心理明细仍必须填写不少于 5 字的原因，并且安全审计记录成功', canDo: '校级处置，但敏感审计失败时同样 fail-closed。' }
  ],
  'sa-card-risk-handle': [
    { role: '辅导员/责任人', roleCode: 'COUNSELOR / CLASS_ADVISOR', permission: '风险相关权限中实际授予的操作', scope: '责任班级/明确学生范围', relation: '风险还必须属于本人责任/当前可办节点', canDo: '接单、处理、跟进本人范围风险。' },
    { role: '学工处/学校管理员', roleCode: 'STUDENT_AFFAIRS_ADMIN / SCHOOL_ADMIN', permission: '对应 risk 管理动作', scope: 'TENANT_ALL', relation: '仍受 NEW/ASSIGNED/PROCESSING/FOLLOWING/ESCALATED/CLOSED 状态机', canDo: '校级调度/升级/授权重开，不直接泄露心理原文。' }
  ],
  'sa-card-archive': [
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN / COLLEGE_SA', permission: '归档相关权限中实际授予的操作', scope: 'COLLEGE', relation: '只能处理本学院档案，并按“学院审核”环节推进', canDo: '学院复核，不代替学工处终审。' },
    { role: '学工处管理员', roleCode: 'STUDENT_AFFAIRS_ADMIN', permission: '对应 archive confirm/manage 动作', scope: 'TENANT_ALL', relation: '材料、档案包和当前版本完整，且状态进入“学工处确认”', canDo: '完成学工归档收口；不能绕过缺失材料。' }
  ]
})
