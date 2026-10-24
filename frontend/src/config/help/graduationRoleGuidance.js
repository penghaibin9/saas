/** V3-03：毕业设计角色 + 权限模板 + 数据范围 + 稳定业务关系说明。 */
export const GRADUATION_ROLE_GUIDANCE = Object.freeze({
  'gd-v3-batch-setup': [
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '批次的查看、新建、编辑、关闭等具体操作权限', scope: '本校毕设全量', relation: '批次必须属于当前租户，动作必须匹配 DRAFT/RUNNING/CLOSED 等当前状态', canDo: '组织本届批次与规则；不能靠角色跳过批次状态机。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '全部权限，或对应的批次管理权限', scope: '本校全量', relation: '仍受租户、批次当前状态和规则校验', canDo: '具备校级管理能力，但不能修改别的租户或把 ARCHIVED 当普通可编辑批次。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '以实际分配的批次管理权限为准', scope: '学生业务数据仍按所属学院范围限定', relation: '批次里的学院范围只是业务配置，不等于授权范围', canDo: '只能执行权限模板真正授予的批次动作；后续学生办理仍不能跨学院。' }
  ],
  'gd-v3-student-mentor': [
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '学生管理、导师管理等实际分配的权限', scope: '本校毕设全量', relation: '学生必须是当前租户 ACTIVE 毕设记录', canDo: '组织学生、导师台账和分配。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '对应 student/mentor 权限', scope: '所属学院', relation: '登录信息必须带有可验证的学院范围，缺失时一律不放行', canDo: '办理本学院学生，不跨学院。' },
    { role: '专业管理员', roleCode: 'GD_MAJOR_ADMIN', permission: '对应 student/mentor 权限', scope: '所属专业', relation: '登录信息必须带有可验证的专业范围', canDo: '办理本专业学生。' },
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: '对应毕业设计查看/指导动作权限', scope: '本人指导学生', relation: '优先按导师台账中的教师工号与当前登录账号匹配', canDo: '办理本人指导学生；导师姓名只作快照，不能据同名扩大权限。' },
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人端点', scope: '仅本人', relation: '只认登录信息中的学号，与毕设学生档案匹配', canDo: '查看/提交本人业务，不按姓名访问他人档案。' }
  ],
  'gd-v2-topic-selection': [
    { role: '学生', roleCode: 'STUDENT', permission: '本人选题端点', scope: '仅本人', relation: '学号对应当前合格的毕设学生，且选题轮次已开放', canDo: '填报本人志愿、按规则发起题目变更；不能操作他人。' },
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: '选题相关权限中实际授予教师的操作', scope: '本人题目/本人指导学生', relation: '稳定导师关系或题目真实 owner 关系', canDo: '处理本人职责内题目，不通过姓名扩大范围。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '选题轮次、题目管理、题目变更等实际权限', scope: '本学院', relation: '学院范围，并与当前轮次、题目批次匹配', canDo: '组织本院选题、审核和变更。' },
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: 'graduationDesign.topic.*', scope: '本校毕设全量', relation: '仍需满足题目审核状态、容量和轮次状态', canDo: '校级管理选题，但不能绕过容量/状态机。' }
  ],
  'gd-v3-taskbook': [
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: 'graduationDesign.taskbook.update / view', scope: '本人指导学生', relation: '学生的导师编号必须能对应到本人的教师工号和登录账号', canDo: '下达和变更本人学生任务书；不能确认他人学生。' },
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人确认端点', scope: '仅本人', relation: '任务书必须属于本人毕设学生记录', canDo: '确认本人名下“待确认”或“变更待确认”的版本。' },
    { role: '授权管理员', roleCode: 'GRADUATION_ADMIN / SCHOOL_ADMIN', permission: '任务书规则允许的代确认，并具备对应权限', scope: '本校授权范围', relation: '代确认是例外路径，必须满足 policy 且原因不少于 5 字', canDo: '受控代确认并单独审计，不能把代确认写成学生本人确认。' }
  ],
  'gd-v2-proposal': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人开题端点', scope: '仅本人', relation: '本人已选题、已确认任务书、资格允许，且没有其他待审/已通过版本', canDo: '提交/被驳回后新版本重交本人开题。' },
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: '开题查看、开题审核权限（以角色模板实际授予为准）', scope: '本人指导学生', relation: '稳定的导师关系，且当前开题为“待审核”', canDo: '办理本人学生开题批阅；不能凭姓名访问他人学生。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: 'graduationDesign.proposal.view / review', scope: '本学院', relation: '学生所属学院在登录范围内', canDo: '办理本学院开题审核。' },
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '对应 proposal 权限', scope: '本校毕设全量', relation: '仍受版本、材料和“待审核”状态约束', canDo: '校级管理/兜底，不覆盖历史版本。' }
  ],
  'gd-v3-guidance-midterm': [
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: 'graduationDesign.guidance.* / midterm.review', scope: '本人指导学生', relation: '稳定导师关系 + 学生阶段/中期状态允许当前动作', canDo: '记录指导、中期检查、复核整改。' },
    { role: '学生', roleCode: 'STUDENT', permission: '本人过程端点', scope: '仅本人', relation: '本人中期记录处于 RECTIFYING 等允许状态', canDo: '提交本人整改、参与本人指导计划签到等学生动作。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '对应 guidance/midterm 权限', scope: '本学院', relation: '学院范围内，且学生处于允许的状态', canDo: '查看/办理本院被授权过程事项。' }
  ],
  'gd-v3-final-submission': [
    { role: '学生', roleCode: 'STUDENT', permission: '学生本人材料提交端点', scope: '仅本人', relation: '本人中期已通过、处于成果检查或答辩阶段、所选文件属于本人可绑定范围', canDo: '提交本人初稿/定稿新版本。' },
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: '成果查看、成果审核权限（以角色模板实际授予为准）', scope: '本人指导学生', relation: '稳定的导师关系，且当前成果为“待审核”', canDo: '办理本人职责内成果审核，定稿通过仍受查重门限制。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: 'graduationDesign.final.view / review', scope: '本学院', relation: '学院范围，并且材料版本与最新一致', canDo: '办理本院成果审核，不能跳过中期/查重。' }
  ],
  'gd-v3-plagiarism': [
    { role: '查重/毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: 'graduationDesign.plagiarism.start / result / disputeReview / view', scope: '本校毕设全量', relation: '任务必须绑定当前学生真实成果，结果回填只处理 CHECKING', canDo: '发起、回填、按权限处理复查；不能修改已完成原结果伪造复查。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '实际授予的 plagiarism.* 权限', scope: '本学院', relation: '学院范围，且目标学生在范围内', canDo: '只办理权限和范围共同允许的本院查重事项。' },
    { role: '学生', roleCode: 'STUDENT', permission: '本人复查申请入口（当前端开放时）', scope: '仅本人', relation: '本人查重已完成且超出阈值', canDo: '对本人超标记录发起正式复查；不能回填结果或审批复查。' }
  ],
  'gd-v3-review': [
    { role: '学院/毕设管理员', roleCode: 'GD_COLLEGE_ADMIN / GRADUATION_ADMIN', permission: '评阅分配、退回、查看等实际权限', scope: '学院 claim 或本校全量', relation: '必须存在 APPROVED 正式定稿，且评阅人与指导教师无 SoD 冲突', canDo: '分配/管理真实评阅任务。' },
    { role: '评阅教师', roleCode: 'GD_REVIEWER', permission: 'graduationDesign.review.submit / view', scope: '本人被分配任务', relation: '只认 GraduationReview.reviewer_mentor_id == 当前用户稳定导师台账 ID', canDo: '提交本人评阅；评阅人姓名仅是快照，真正授权不看姓名；缺稳定 reviewer_mentor_id 时 fail-closed。' }
  ],
  'gd-v2-defense': [
    { role: '答辩秘书', roleCode: 'GD_DEFENSE_SECRETARY', permission: '答辩评分确认、查看等实际权限', scope: '本人所在答辩组学生', relation: '只认 GraduationDefenseGroup.secretary_mentor_id 与当前导师身份匹配', canDo: '办理本人答辩组秘书职责和允许的确认动作。' },
    { role: '答辩评委', roleCode: 'GD_DEFENSE_EXPERT', permission: 'graduationDesign.defense.score', scope: '本人所在答辩席位学生', relation: '只认稳定的导师编号或专家席位，不按姓名匹配', canDo: '录入本人席位评分；不能代其他评委。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: 'graduationDesign.defense.groupManage / publish / view', scope: '本学院', relation: '学院 claim + 答辩组/学生同批次且满足定稿与回避规则', canDo: '编排和发布本院被授权答辩。' },
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '对应 defense.* 权限', scope: '本校毕设全量', relation: '仍受稳定席位、导师回避、学生阶段和 published 状态约束', canDo: '校级管理答辩，不绕过席位冲突。' }
  ],
  'gd-v2-grade': [
    { role: '成绩管理员', roleCode: 'GD_GRADE_ADMIN', permission: '成绩核算、审核、发布、撤回、查看等实际权限', scope: '本校毕设全量', relation: '必须有权威定稿、COMPLETED 评阅、CONFIRMED 答辩来源且状态允许', canDo: '按分离动作核算、复核、发布/撤回；不能直接手改来源。' },
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '实际授予的成绩相关权限', scope: '本校毕设全量', relation: '仍受评阅、答辩来源是否一致及成绩状态流转约束', canDo: '只能执行权限模板明确授予的成绩动作。' },
    { role: '指导教师', roleCode: 'GD_MENTOR', permission: '实际授予的 grade view / advisor score 类动作', scope: '本人指导学生', relation: '稳定导师关系；最终综合成绩不由导师个人直接发布', canDo: '办理本人职责内来源/查看动作，不能把指导分当最终成绩。' },
    { role: '学生', roleCode: 'STUDENT', permission: '本人端点', scope: '仅本人', relation: '本人已有 PUBLISHED 成绩才可进入申诉链', canDo: '查看本人正式成绩、按规则申诉；不能查看他人或直接改分。' }
  ],
  'gd-v3-archive': [
    { role: '毕设管理员', roleCode: 'GRADUATION_ADMIN', permission: '归档备案、导出等实际权限', scope: '本校毕设全量', relation: '学生必备材料完整、没有未处理风险，且状态处于“待提交”“已提交”等允许的环节', canDo: '生成、提交/备案、导出被授权归档；FILED 后不能改证据。' },
    { role: '学院管理员', roleCode: 'GD_COLLEGE_ADMIN / COLLEGE_ADMIN', permission: '实际授予的 archive 权限', scope: '本学院', relation: '学院范围内，并且学生归档状态、材料完整性满足要求', canDo: '办理本院被授权归档动作；不能跨学院或绕过开放风险。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '* 或对应 archive 权限', scope: '本校全量', relation: '仍受 Manifest、SHA-256、状态机和 ORM 终态不可变守卫', canDo: '校级归档管理；当前没有直接修改 FILED 证据的合法后门。' }
  ]
})
