/**
 * Help Center V3 · 角色/数据范围/业务关系解释层。
 *
 * 注意：这里是帮助展示真值，不参与授权。真正能否操作始终由后端：
 * permissionCode + data scope + business ownership/relation + current state 共同裁决。
 */
export const HELP_AUTHORIZATION_PRINCIPLE =
  '帮助中的角色只说明常见职责，不是授权凭证。真正能否办理 = 当前角色权限模板（permissionCode）+ 数据范围 + 业务关系/记录归属 + 当前业务状态；任一条件不满足，后端都可以拒绝。'

export const ACADEMIC_ROLE_GUIDANCE = Object.freeze({
  'aa-card-status-change': [
    { role: '辅导员', roleCode: 'COUNSELOR', permission: 'academicAffairs.statusChange.counselorReview', scope: '本人所带班级', relation: '当前申请必须处于辅导员审批节点，且学生属于本人负责班级', canDo: '办理本人班级学生的辅导员节点；不能越过学院/教务终审。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*（具体节点仍由 service 校验）', scope: '本学院', relation: '原学院/目标学院与当前审批节点必须匹配', canDo: '办理本学院节点；转专业等跨学院流程按转出/转入节点分别收敛。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.statusChange.officeReview / academicAffairs.*', scope: '本校教务全量', relation: '必须到达教务终审节点', canDo: '执行教务终审并让学籍异动正式生效。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍需满足当前审批节点与状态机', canDo: '可处理本校范围管理动作，但不能绕过状态机直接改事实。' }
  ],
  'aa-card-grade-entry': [
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.grade.view / input / submit', scope: '本人授课课程', relation: '必须与成绩任务存在真实授课/教学任务关系', canDo: '录入并提交本人课程成绩；不能学院审核、教务发布。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '成绩任务必须属于本学院数据范围', canDo: '可按学院职责查看/管理，但不能把通配权限理解为跨学院或跳过正式审核链。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '仍受成绩任务状态和正式教学名单约束', canDo: '负责校级教务管理；普通教师录分场景不应使用管理员身份代替真实授课关系。' }
  ],
  'aa-card-grade-review-publish': [
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.* / 对应成绩审核权限', scope: '本学院', relation: '必须处于学院审核节点且任务归属本学院', canDo: '学院审核、退回；不能替代教务处做最终正式发布。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '必须已完成前置审核且发布门校验通过', canDo: '教务终审与正式发布。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍需满足成绩状态、名单快照和发布门', canDo: '具备本校管理能力，但不能靠角色绕过成绩正式化规则。' }
  ],
  'aa-card-grade-change': [
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.gradeChange.apply', scope: '本人授课课程', relation: '只能对本人具有真实授课关系的正式成绩发起更正', canDo: '发起更正并说明原因；不能直接覆盖已发布成绩。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.* / 对应更正审核权限', scope: '本学院', relation: '申请与学生/课程须在本学院职责范围且处于当前审核节点', canDo: '学院节点审核。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '必须按更正审批链到达教务节点', canDo: '完成高权限复核，使新版本成为有效正式成绩。' }
  ],
  'aa-card-selection-round': [
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.selection.*', scope: '本校教务全量', relation: '轮次必须属于当前学校/批次且状态允许配置', canDo: '配置、开放和管理选课轮次。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '只有被授权到本学院的选课数据才能办理', canDo: '在本学院范围参与选课管理，跨学院动作仍由后端范围收敛。' },
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.selection.view / rosterView', scope: '本人授课课程', relation: '必须是对应教学任务任课教师', canDo: '查看轮次和本人课程选课名单；不能开关轮次或发布选课。' }
  ],
  'aa-card-selection-publish': [
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.selection.*', scope: '本校教务全量', relation: '轮次必须已按规则完成关闭/抽签等前置步骤', canDo: '执行正式发布并形成服务器端选课事实。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '仅能办理服务端允许的本学院节点', canDo: '辅助本学院选课管理；最终发布能力仍以具体端点二次角色校验为准。' }
  ],
  'aa-card-exam-arrangement': [
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.exam.*', scope: '本校教务全量', relation: '考试任务、考生名单、教室和监考资源必须属于当前学校且满足排考规则', canDo: '组织自动/人工排考并处理冲突。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '考试任务需在本学院授权范围', canDo: '办理本学院考务管理动作，跨学院资源仍由服务端裁决。' },
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.exam.view / recordAbnormal', scope: '本人相关考试', relation: '必须与课程或监考任务存在业务关系', canDo: '查看安排、登记允许的考场异常；不能排考或发布。' }
  ],
  'aa-card-exam-publish': [
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.exam.*', scope: '本校教务全量', relation: '必须通过考场、座位、监考完整性和冲突校验', canDo: '正式发布考试安排。' },
    { role: '学校管理员', roleCode: 'SCHOOL_ADMIN', permission: '*', scope: '本校全量', relation: '仍受考务发布门和状态机约束', canDo: '具备管理能力，但不能发布不完整或冲突的考试安排。' }
  ],
  'aa-v3-program-course': [
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*（course/program 对应权限）', scope: '本学院', relation: '课程开课单位、专业和方案归属必须属于本学院', canDo: '维护/审核本院基础数据；不能跨学院改课程或方案。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '仍需满足课程/方案当前版本与审核状态', canDo: '完成教务审核、发布和校级管理。' },
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.course.view / program.view', scope: '教学职责相关只读', relation: '没有课程/方案管理业务关系时仅查看', canDo: '查看课程库和培养方案；不拥有课程维护、方案审核发布权。' }
  ],
  'aa-v3-teaching-task': [
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.teachingTask.view', scope: '本人教学任务', relation: 'teacher_key 必须稳定对应当前账号', canDo: '查看并按本人归属完成教师确认；不能确认他人任务或批量管理任务。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '任务所属学院/班级需在本人数据范围', canDo: '生成、分配和学院核对本院教学任务。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '必须完成教师确认和学院前置核对', canDo: '教务终审并将合格任务推进到 READY。' }
  ],
  'aa-v3-schedule': [
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.schedule.view / teacherConfirm', scope: '本人课表', relation: '必须与教学任务/课表项存在本人授课关系', canDo: '查看本人课表、提出/确认允许的教师侧动作；不能做全校排课。' },
    { role: '辅导员', roleCode: 'COUNSELOR', permission: 'academicAffairs.schedule.view', scope: '本人所带班级', relation: '只能查看本班课表', canDo: '查看负责班级课表；不能查看任意教师/教室课表或执行排课管理。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '排课任务和教学班须落在本学院职责范围', canDo: '办理本院排课相关工作。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '只消费 READY 教学任务并通过预发布校验', canDo: '全校排课、预发布和正式发布。' }
  ],
  'aa-v3-credit-gpa': [
    { role: '任课教师', roleCode: 'ACADEMIC_TEACHER', permission: 'academicAffairs.process.view / grade.view', scope: '本人教学职责相关', relation: '只能查看本人课程或服务端允许的学业过程数据', canDo: '查看相关学业结果，不直接维护学生累计学分/GPA。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '学分/GPA来自有效正式成绩，不存在“手工改聚合值”的普通业务关系', canDo: '查看和核对正式聚合；源成绩异常应回到成绩更正/补考链修复。' },
    { role: '学生', roleCode: 'STUDENT', permission: '本人端点', scope: '仅本人', relation: '账号必须解析到本人学生主档', canDo: '查看本人学分/GPA结果，不能查看或修改他人学业数据。' }
  ],
  'aa-v3-makeup-retake': [
    { role: '任课教师/录分教师', roleCode: 'ACADEMIC_TEACHER', permission: '对应补考录分/教学权限（具体端点继续校验）', scope: '本人被分配任务', relation: '必须是当前补考任务的真实办理教师', canDo: '在被分配的补考任务中录入允许的成绩；不能跳过学院审核与教务发布。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '补考记录需属于本学院审核范围', canDo: '办理学院审核。' },
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '必须来自已发布不及格正式成绩且前置审核完成', canDo: '正式发布补考结果并触发有效成绩/学分聚合更新。' }
  ],
  'aa-v3-graduation-qualification': [
    { role: '教务处管理员', roleCode: 'ACADEMIC_ADMIN', permission: 'academicAffairs.*', scope: '本校教务全量', relation: '必须能唯一解析学生适用培养方案与有效正式成绩证据', canDo: '组织毕业资格核验并处理不能自动判定的证据问题。' },
    { role: '学院管理员', roleCode: 'COLLEGE_ADMIN', permission: 'academicAffairs.*', scope: '本学院', relation: '仅处理本学院学生和本院职责范围内证据', canDo: '核对本院学生资格材料；跨学院/校级终审仍按权限收口。' },
    { role: '学生', roleCode: 'STUDENT', permission: '本人端点', scope: '仅本人', relation: '账号必须解析到本人学生主档', canDo: '查看本人资格结论/缺口；不能修改培养方案、有效成绩或审核证据。' }
  ]
})

export function attachAcademicRoleGuidance(cards) {
  return cards.map((card) => ({
    ...card,
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    roleGuidance: ACADEMIC_ROLE_GUIDANCE[card.id] || []
  }))
}
