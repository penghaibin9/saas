/**
 * V3-02 岗位实习角色说明。
 * 仅用于帮助展示；真正鉴权仍由 permissionCode + 数据范围 + 稳定指导关系/本人关系 + 状态机共同裁决。
 */
export const INTERNSHIP_ROLE_GUIDANCE = Object.freeze({
  'in-v3-batch-lifecycle': [
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: 'internship.batch.manage', scope: '本校全量 / ADMIN_TENANT', relation: '批次是全校级作业，当前上下文必须解析为 ADMIN_TENANT', canDo: '新建、编辑、启用、结束、归档和作废批次；仍必须遵守状态机、版本与 readiness。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: '角色模板虽含 internship.batch.manage', scope: '本学院 / SCOPED', relation: 'service 的 assert_admin_tenant 会继续拒绝全校级批次写操作', canDo: '可参与本院实习业务，但不能因为模板里有 batch.manage 就执行校级批次状态变更。' }
  ],
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
  'in-v3-onboard-compliance': [
    { role: '学生', roleCode: 'STUDENT', permission: '本人端点对应的安全/知情/材料动作', scope: '仅本人', relation: '只能完成本人需要提交/确认的合规证据', canDo: '补齐本人材料和确认项；不能把自己标记为合规通过或审批豁免。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.compliance.view + consent/safety/filing/incident 等明确权限', scope: '本人指导学生', relation: '稳定 advisor_user_id + 对应证据/记录归属', canDo: '查看本人学生合规结果并办理模板明确授予的证据动作；compliance.view 本身不是全域写权。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: '学院实习合规权限集', scope: '本学院', relation: '学生、企业和证据必须在本院授权范围', canDo: '办理本院合规审核、保险/备案等被授予动作。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍受冻结规则、证据状态和版本约束', canDo: '校级合规管理和例外收口；不能手工把 blocker 改成通过而没有正式证据。' }
  ],
  'in-v2-teacher-process': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.report.review / guidance.* / visit.* / risk.handle 等', scope: '本人指导学生', relation: '授权只认稳定 advisor_user_id；姓名只作展示', canDo: '批阅周报/过程材料、记录指导巡访、处理本人学生风险与异常。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: '学院实习权限集', scope: '本学院', relation: '学生/记录必须落在本学院数据范围', canDo: '查看并办理本院过程管理、风险和整改事项。' },
    { role: '安全审计员', roleCode: 'SECURITY_AUDITOR', permission: 'internship.dashboard/student/risk/stats/...view', scope: '监督只读', relation: '没有业务 owner 关系也不获得写权限', canDo: '查看风险、统计、审核/分配台账用于监督；不做周报审批、风险处置等写操作。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍受记录状态和流程动作约束', canDo: '本校管理与异常兜底，不以“管理员看过”代替正式关闭。' }
  ],
  'in-v3-risk-incident': [
    { role: '学生', roleCode: 'STUDENT', permission: '本人求助/风险上报端点', scope: '仅本人', relation: '账号必须解析到本人当前实习记录', canDo: '提交本人求助形成真实风险单；不能自行受理、升级或关闭。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.risk.view / handle；internship.incident.view / report / handle', scope: '本人指导学生', relation: '稳定 advisor_user_id 必须命中', canDo: '受理、跟进、升级和关闭本人学生风险，并处理被授予的事故动作。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.risk.handle / incident.handle 等学院权限', scope: '本学院', relation: '风险/事故对应学生必须属于本学院', canDo: '办理本院风险和事故处置。' },
    { role: '安全审计员', roleCode: 'SECURITY_AUDITOR', permission: 'internship.risk.view 等监督只读', scope: '监督只读', relation: '看见记录不建立 owner 写关系', canDo: '查看风险、统计和审计台账；不执行受理/升级/关闭。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍需符合风险/事故状态机', canDo: '校级处置与兜底；不能跳过正式状态链。' }
  ],
  'in-v2-student-change': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人变更端点', scope: '仅本人', relation: '只能对本人当前正式实习去向发起变更', canDo: '申请换岗、换单位、转自主或退岗，并撤回本人 PENDING 申请。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.change.view / review', scope: '本人指导学生', relation: '稳定指导关系 + 当前变更处于本人可审核节点', canDo: '审核本人指导学生变更；不能处理无指导关系学生。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.change.view / review', scope: '本学院', relation: '学生与目标事实需在本院职责范围', canDo: '办理本院变更审核；跨学院/校级规则仍以后端为准。' }
  ],
  'in-v2-enterprise-eval': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.eval.enterprise.view / manage / review', scope: '本人指导学生', relation: '必须是本人指导学生，评价证据属于该实习记录', canDo: '依据真实企业评价材料代录本人学生企业评价；最终审核仍需满足录审分离和审核角色规则。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.eval.enterprise.*', scope: '本学院', relation: '评价记录属于本院学生', canDo: '办理本院企业评价复核与台账工作。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍需真实企业证据和审核状态', canDo: '本校管理；当前不能宣传为企业账号登录在线评分闭环。' }
  ],
  'in-v3-student-evaluation': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人鉴定端点', scope: '仅本人', relation: '账号必须解析到本人实习记录', canDo: '提交/退回后重交本人自评；APPROVED 后不能直接改。' },
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.eval.advisor.manage；模板同时含 eval.self.review 也不代表可终审', scope: '本人指导学生', relation: '稳定指导关系 + 当前鉴定为 SUBMITTED/PENDING', canDo: '填写指导教师意见；学校终审有独立角色白名单，指导教师不能自己写意见又自己终审。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.eval.self.review', scope: '本学院', relation: '鉴定属于本院学生且指导意见已完成', canDo: '执行学校侧授权审核/退回。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '* / internship.eval.self.review', scope: '本校全量', relation: '仍须存在当前版本指导意见并通过状态/版本校验', canDo: '执行学校审核收口。' }
  ],
  'in-v2-score': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.score.view / manage', scope: '本人指导学生', relation: '稳定指导关系且成绩记录在本人范围', canDo: '核算本人指导学生成绩；没有 internship.score.publish，不能做最终发布/撤回。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.score.view / manage', scope: '本学院', relation: '成绩属于本院学生且处于 PENDING_REVIEW', canDo: '执行授权复核/退回重算；最终发布、撤回、归档仍不是学院权限。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '* + score publish 所需权限', scope: '本校全量', relation: '必须通过缺项、状态、版本和数据范围校验', canDo: '唯一普通学校角色可最终发布、撤回和归档实习成绩。' },
    { role: '安全审计员', roleCode: 'SECURITY_AUDITOR', permission: 'internship.stats.score.view 等只读', scope: '监督只读', relation: '不参与成绩正式化审批', canDo: '用于监督和统计，不得核算/发布成绩。' }
  ],
  'in-v3-archive': [
    { role: '实习指导教师', roleCode: 'INTERN_MENTOR', permission: 'internship.archive.view / prepare', scope: '本人指导学生', relation: '稳定指导关系', canDo: '查看本人学生归档就绪情况并准备材料；当前模板不授予 archive.execute/force。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'internship.archive.view / execute / package', scope: '本学院', relation: '学生必须在本学院数据范围并通过 ARCHIVE 合规评估', canDo: '执行本院普通归档和归档包；不能强制归档。' },
    { role: '就业教师', roleCode: 'EMPLOYMENT_TEACHER', permission: 'internship.archive.view / package', scope: '就业/归档统计职责范围', relation: '不建立学生归档审批 owner 权', canDo: '查看归档结果、生成授权归档包和统计；不执行学生强制归档。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*（execute/package/force/revoke）', scope: '本校全量', relation: '普通归档需 passed；force 还需≥10个汉字原因和依据文件', canDo: '执行校级归档及严格受控的强制归档。' }
  ]
})
