/**
 * V3-02 岗位实习角色说明。
 * 仅用于帮助展示；真正鉴权仍由 permissionCode + 数据范围 + 稳定指导关系/本人关系 + 状态机共同裁决。
 */
export const INTERNSHIP_ROLE_GUIDANCE = Object.freeze({
  'in-v2-student-application': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人端点', scope: '仅本人', relation: '账号必须解析到本人实习记录', canDo: '保存、提交、撤回本人申请；不能审核他人申请。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.application.view / review', scope: '本人指导学生', relation: 'InternshipRecord.advisor_user_id 必须稳定等于当前 userId', canDo: '审核本人指导学生申请；姓名相同不构成授权。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.application.view / review（来自学院实习权限集）', scope: '本学院', relation: '学生/实习记录必须在本学院范围', canDo: '办理本院申请审核；不能跨学院。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍须满足申请状态、岗位容量和批次规则', canDo: '可处理本校范围管理动作，但不能绕过状态机和容量校验。' }
  ],
  'in-v2-agreement': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人协议端点', scope: '仅本人', relation: '协议必须属于本人实习记录', canDo: '确认本人协议；不能代企业/学校完成确认。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.agreement.view / manage / sign', scope: '本人指导学生', relation: '稳定 advisor_user_id 关系 + 当前协议状态允许', canDo: '生成、下发、记录真实企业签署材料、学校确认/驳回等本人学生协议动作。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.agreement.*（学院权限集）', scope: '本学院', relation: '协议对应学生必须属于本学院', canDo: '办理本院协议管理和模板相关职责。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍须满足协议状态与版本校验', canDo: '本校协议管理；不能把扫描件帮助写成已接入电子签章。' }
  ],
  'in-v2-student-change': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人变更端点', scope: '仅本人', relation: '只能对本人当前正式实习去向发起变更', canDo: '申请换岗、换单位、转自主或退岗，并撤回本人 PENDING 申请。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.change.view / review', scope: '本人指导学生', relation: '稳定指导关系 + 当前变更处于本人可审核节点', canDo: '审核本人指导学生变更；不能处理无指导关系学生。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.change.view / review', scope: '本学院', relation: '学生与目标事实需在本院职责范围', canDo: '办理本院变更审核；跨学院/校级规则仍以后端为准。' }
  ],
  'in-v2-teacher-process': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.report.review / guidance.* / visit.* / risk.handle 等', scope: '本人指导学生', relation: '授权只认稳定 advisor_user_id；姓名只作展示', canDo: '批阅周报/过程材料、记录指导巡访、处理本人学生风险与异常。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: '学院实习权限集', scope: '本学院', relation: '学生/记录必须落在本学院数据范围', canDo: '查看并办理本院过程管理、风险和整改事项。' },
    { role: '安全审计员', roleCode: 'SECURITY_AUDITOR', permission: 'internship.dashboard/student/risk/stats/...view', scope: '监督只读', relation: '没有业务 owner 关系也不获得写权限', canDo: '查看风险、统计、审核/分配台账用于监督；不做周报审批、风险处置等写操作。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍受记录状态和流程动作约束', canDo: '本校管理与异常兜底，不以“管理员看过”代替正式关闭。' }
  ],
  'in-v2-enterprise-evaluation': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.eval.enterprise.view / manage / review', scope: '本人指导学生', relation: '必须是本人指导学生，评价证据属于该实习记录', canDo: '依据真实企业评价材料代录并审核本人学生的企业评价。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.eval.enterprise.*', scope: '本学院', relation: '评价记录属于本院学生', canDo: '办理本院企业评价复核与台账工作。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍需真实企业证据和审核状态', canDo: '本校管理；当前不能宣传为企业账号登录在线评分闭环。' }
  ],
  'in-v2-score': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.score.view / manage', scope: '本人指导学生', relation: '稳定指导关系且成绩记录在本人范围', canDo: '核算本人指导学生成绩；没有 internship.score.publish，不能做最终发布/撤回。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.score.view / manage', scope: '本学院', relation: '成绩属于本院学生且处于 PENDING_REVIEW', canDo: '执行授权复核/退回重算；最终发布、撤回、归档仍不是学院权限。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '* + score publish 所需权限', scope: '本校全量', relation: '必须通过缺项、状态、版本和数据范围校验', canDo: '唯一普通学校角色可最终发布、撤回和归档实习成绩。' },
    { role: '安全审计员', roleCode: 'SECURITY_AUDITOR', permission: 'internship.stats.score.view 等只读', scope: '监督只读', relation: '不参与成绩正式化审批', canDo: '用于监督和统计，不得核算/发布成绩。' }
  ]
})
