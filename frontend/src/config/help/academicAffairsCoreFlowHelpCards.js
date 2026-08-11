/**
 * Help Center V3-01 · 教务完整事实链新增正式任务卡。
 *
 * 这些卡只覆盖本轮再次对照 PC 路由、后端 service、权限码、数据范围与状态机确认的节点。
 * 学籍、选课、考务、成绩继续复用 academicAffairsCleanHelpCards.js 的 V2 真值，不复制正文。
 */
export const ACADEMIC_AFFAIRS_CORE_FLOW_HELP_CARDS = [
  {
    id: 'aa-v3-program-course',
    module: '教务中心 · 课程与培养方案',
    title: '课程库和培养方案怎样准备，什么时候才能用于后续教学任务',
    roles: ['教务人员', '学院管理员', '学校管理员'],
    route: '/admin/academic-affairs/programs',
    entry: '教务中心 → 课程库 / 培养方案',
    keywords: ['课程库', '培养方案', '课程审核', '方案审核', '方案发布', '绑定年级', '学分要求', '版本', 'ENABLED'],
    summary: '课程与培养方案都是版本化正式基础数据。课程按 DRAFT/RETURNED → COLLEGE_REVIEW → ACADEMIC_REVIEW → ENABLED 审核；培养方案提交前必须设置毕业总学分且方案课程学分合计达到要求，经学院审、教务审发布后再绑定年级，进入 ENABLED 才能作为教学任务生成依据。',
    prerequisites: [
      '先确认当前学校学院、专业、年级、行政班等组织基础数据已经建立。',
      '课程应有稳定课程代码、名称、性质、类别、学分/学时和开课单位；分项学时存在时，其合计必须与总学时一致。',
      '培养方案提交前必须设置毕业总学分，并把真实课程版本纳入方案；方案课程学分合计不能低于毕业总学分。'
    ],
    permissions: [
      '课程查看/维护/审核分别受 academicAffairs.course.view、academicAffairs.course.manage、academicAffairs.course.approve 控制；学院管理员维护课程时还受本学院开课单位数据范围限制。',
      '培养方案查看、维护、提交、审核、发布分别受 academicAffairs.program.view/manage/submit/review/publish 控制。',
      '页面可见不等于可以审核或发布；后端权限码、租户和学院数据范围是最终边界。'
    ],
    steps: [
      '先在「课程库」建立课程。课程编号需满足当前格式规则；课程负责人如填写，必须是本校在职教师；适用专业如填写，必须是本租户启用专业。',
      '课程从 DRAFT/RETURNED 提交审核，经学院审核进入 ACADEMIC_REVIEW，再由教务审核进入 ENABLED。已启用课程再次修改时不会原地覆盖，而是建立新版本并保留 prevVersionId 链。',
      '进入「培养方案」新建方案，设置专业、年级、毕业总学分、课程模块和开课学期等，并核对页面返回的 creditSum / creditGap。',
      '方案只有 DRAFT/RETURNED 可直接编制。提交时服务端再次校验毕业总学分已设置、课程学分合计已达到要求，否则阻断提交。',
      '方案按 COLLEGE_REVIEW → ACADEMIC_REVIEW → PUBLISHED 两级审核；退回必须填写不少于 5 字原因，回到 RETURNED 修改重提。',
      'PUBLISHED 方案再绑定具体年级/班级后进入 ENABLED。同专业同年级旧 ACTIVE 绑定会变为 SUPERSEDED，历史年级继续保留原版本关系。'
    ],
    warnings: [
      '不要直接修改已经 ENABLED 的课程来改变历史事实；服务端会强制新版本，历史引用继续锁定旧版本。',
      '课程仍被审核中、已发布、已启用或冻结的培养方案引用时不能直接停用。',
      '培养方案不是“保存完就能排课”；必须完成审核、发布并形成有效年级绑定，后续教学任务才有可靠来源。'
    ],
    successCriteria: [
      '本学期要使用的课程已完成审核并有稳定 ENABLED 版本。',
      '适用年级的培养方案已完成两级审核、PUBLISHED 并形成 ACTIVE 年级/班级绑定，方案状态进入 ENABLED。',
      '方案总学分、课程明细和模块要求可以被后续教学任务及毕业资格审核稳定解析。'
    ],
    nextSteps: [
      '课程与培养方案准备完成后，进入「教学任务」按当前学期和学院生成应开课程任务。',
      '如果只是修改未来年级方案，应使用新版本/新绑定，不要改写已经被历史学生使用的事实版本。'
    ],
    troubleshooting: [
      '方案提交提示毕业总学分未设置或课程学分不足：先补齐总学分和课程明细，直到 creditGap 不再为正。',
      '课程停用被阻断：查看课程引用情况，确认是否仍被在途或已生效培养方案引用。',
      '学院管理员提示开课单位无数据范围：检查课程开课单位是否属于本人学院。',
      '同年级学生后续解析到错误方案：检查专业、gradeYear、classId 和 ACTIVE 绑定，不要靠列表顺序猜适用方案。'
    ],
    contactAdminWhen: [
      '同一专业/年级出现无法判断的多条有效培养方案绑定，已经影响学生适用方案解析。',
      '课程历史版本或方案绑定关系与学校正式制度不一致，需要做数据修复而不是普通编辑。',
      '账号已经具备岗位职责但缺少对应 course/program 权限码或学院数据范围。'
    ],
    related: [
      { label: '课程库', route: '/admin/academic-affairs/courses' },
      { label: '培养方案控制台', route: '/admin/academic-affairs/programs/console' },
      { label: '教学任务', route: '/admin/academic-affairs/teaching-tasks' }
    ]
  },
  {
    id: 'aa-v3-teaching-task',
    module: '教务中心 · 教学任务',
    title: '如何从培养方案生成教学任务、分配教师并确认到可排课状态',
    roles: ['教务人员', '学院管理员', '任课教师', '学校管理员'],
    route: '/admin/academic-affairs/teaching-tasks',
    entry: '教务中心 → 教学任务',
    keywords: ['教学任务', '生成任务', '任课教师分配', '教师确认', '合班', '拆班', 'READY', 'COLLEGE_CONFIRMED', 'APPROVED'],
    summary: '教学任务按已启用培养方案和 ACTIVE 年级绑定生成课程×行政班任务，同学期同学院生成幂等。任务先分配稳定教师身份，由教师本人确认，再经学院核对和教务终审；终审通过后已确认任务进入 READY，才能成为正式排课来源。',
    prerequisites: [
      '当前学期已建立且仍可写；学期归档/冻结写保护未阻断当前操作。',
      '适用培养方案已经 ENABLED，并存在 ACTIVE 年级或班级绑定；方案中的课程必须引用真实 courseId。',
      '需要分配的教师应有稳定教师工号/登录标识，避免只靠姓名建立教学归属。'
    ],
    permissions: [
      '生成/分配使用 academicAffairs.teachingTask.manage；批次学院核对和教务终审使用 academicAffairs.teachingTask.confirm。',
      '教师确认接口虽然可从任务查看入口进入，但服务端会按稳定 teacher_key 校验本人授课范围；普通教师无法确认他人任务。',
      '合班拆班、教学任务调整分别要求 teachingTask.merge / teachingTask.adjust，不能用列表可见性代替写权限。'
    ],
    steps: [
      '按当前学期和学院生成教学任务批次。系统读取 ENABLED 培养方案和 ACTIVE 绑定，为应开课程×目标班级建立任务；同批次已存在的课程×班级不会重复生成。',
      '为 PENDING_ASSIGN / 被教师退回的任务分配任课教师，核对周学时、总学时、起止周和预计人数。',
      '需要合班时，只能在教师确认前对同批次、同课程的 2 条以上任务合并；拆班同样必须在确认前完成。',
      '任课教师在本人任务中确认或退回。退回需填写不少于 5 字原因；未绑定稳定 teacher_key 的历史任务对普通教师 fail-closed，应由管理端修复归属。',
      '学院核对批次后进入 COLLEGE_CONFIRMED，再由教务终审。终审 APPROVE 后批次为 APPROVED，已 TEACHER_CONFIRMED 的任务转为 READY。',
      '如 READY 后仍需更正教师、学时、周次或人数，使用“教学任务调整”并填写不少于 5 字原因；若该任务已经生成课表项，必须先处理对应课表，服务端禁止静默改任务。'
    ],
    warnings: [
      '教学任务生成依赖正式培养方案绑定，不要手工把“应该开的课”当成唯一事实来源。',
      '合班/拆班只能发生在教师确认前；确认后要先按正式流程退回，不能直接改教学班组成。',
      '已生成课表项的任务不能静默修改教师或学时，否则会造成任务与课表事实分叉，服务端会直接阻断。'
    ],
    successCriteria: [
      '批次通过学院核对和教务终审，状态为 APPROVED。',
      '需要排课的教学任务均有真实课程、稳定教师归属、合理周次/学时，并进入 READY。',
      '教师确认、退回、合班拆班和调整都有审计轨迹。'
    ],
    nextSteps: [
      'READY 教学任务进入「课表管理 / 排课管理」，作为手工排课、导入或自动排课的唯一正式任务来源。',
      '排课前先处理教师退回任务、未分配任务和学时/周次异常，避免到课表阶段再返工。'
    ],
    troubleshooting: [
      '生成后没有任务：检查方案是否 ENABLED、绑定是否 ACTIVE、课程明细是否有 courseId，以及学院/班级是否在当前数据范围。',
      '教师看得到但无法确认：检查 teacher_key 是否稳定绑定本人账号；只有姓名没有稳定工号的历史任务不会放行。',
      '批次不能终审：确认已经先完成学院核对，且待分配/教师退回任务已收口。',
      '调整任务提示已经有课表项：先去课表管理调整或作废相关排课，再回来改教学任务。'
    ],
    contactAdminWhen: [
      '教师工号/登录标识与教学任务 teacher_key 无法对应，导致正确教师长期无法确认。',
      '培养方案与班级绑定正确但重复生成或长期缺失任务，需要检查历史数据唯一性。',
      '任务已经进入正式课表，但发现课程身份或教学班事实从源头就错，需要跨模块修复。'
    ],
    related: [
      { label: '任课教师分配', route: '/admin/academic-affairs/teaching-tasks/assign' },
      { label: '教师任务确认', route: '/admin/academic-affairs/teaching-tasks/teacher-confirm' },
      { label: '课表管理', route: '/admin/academic-affairs/schedule' }
    ]
  },
  {
    id: 'aa-v3-schedule',
    module: '教务中心 · 排课',
    title: '如何把 READY 教学任务排成课表并完成预发布、正式发布',
    roles: ['教务人员', '学院管理员', '学校管理员'],
    route: '/admin/academic-affairs/schedule',
    entry: '教务中心 → 课表管理 / 排课管理',
    keywords: ['排课', '课表', 'READY', '冲突', '教室容量', '周学时', '预发布', 'PRE_PUBLISHED', 'PUBLISHED'],
    summary: '课表只能消费同学期已终审教学任务批次中的 READY 任务。每条排课都会校验教学周、作息节次、单双周、教师/班级/教室冲突、教室类型与容量及周学时上限；正式发布必须先通过预发布门，不能从 DRAFT 直接发布。',
    prerequisites: [
      '当前学期、教学周和学校启用作息节次已经正确配置。',
      '对应教学任务批次已经 APPROVED，需要排课的任务已经 READY，并有有效周学时、起止周和教师归属。',
      '需要校验类型/容量的教室必须能匹配真实教室字典，不能只填一个无法识别的自由文本名称。'
    ],
    permissions: [
      '课表查看受 academicAffairs.schedule.view 控制；维护、预发布和正式发布使用服务端对应 schedule 编辑权限。',
      '教室等资源仍受当前租户与数据范围约束；页面可选并不代表服务端会跳过资源状态和冲突检查。'
    ],
    steps: [
      '新建当前学期课表批次，状态从 DRAFT 开始。',
      '通过手工、导入或已接入的自动排课把 READY 教学任务落成课表项；没有 taskId 时必须用课程名称+教师工号或班级唯一匹配，匹配多条会要求明确教学任务ID。',
      '为每条排课选择星期、启用节次、起止周、单双周和教室。排课周次必须位于教学任务自身起止周内，不能超过任务周学时。',
      '处理教师、班级、教室冲突及教室类型/容量不满足等 409；不要通过重复点击绕过冲突。',
      '处理教师异议和发布门阻断后执行预发布。只有 DRAFT 批次、无未处理教师异议且通过完整性 gate 才能进入 PRE_PUBLISHED。',
      '预发布后如果再新增、移动、导入或调整课表，批次会重新回到 DRAFT，需要再次预发布。确认无误后从 PRE_PUBLISHED 正式发布为 PUBLISHED。'
    ],
    warnings: [
      '已发布课表不能直接编辑；需要后续调整时应走正式调停课/作废重发通道并留审计。',
      '不要把“页面显示没有冲突”理解成最终保证，保存和发布时服务端会重新校验。',
      '正式发布是幂等的；已经 PUBLISHED 时不要靠重复发布解决通知或数据问题。'
    ],
    successCriteria: [
      '全部需要排课的 READY 任务满足发布门要求，没有阻断级冲突或未处理教师异议。',
      '批次按 DRAFT → PRE_PUBLISHED → PUBLISHED 完成，并产生正式发布记录。',
      '班级、教师、教室、学生等课表视图读取到同一正式发布结果。'
    ],
    nextSteps: [
      '课表发布后进入选课管理：配置/发布选课批次和轮次，学生最终选课仍以后端资格、时间窗、冲突和容量事务为准。',
      '后续需要临时调课/停课时走「调停课」链，不回头直接修改已发布课表。'
    ],
    troubleshooting: [
      '提示教学任务不存在或未 READY：回到教学任务，确认批次已教务终审且任务已进入 READY。',
      '提示节次未启用或周次越界：检查当前学期教学周、学校作息和任务起止周。',
      '提示教室不可用/容量不足/类型不符：更换符合条件的教室或先修正教室字典。',
      '预发布失败：先处理教师异议和发布 gate 返回的缺失/冲突，不要直接尝试正式发布。'
    ],
    contactAdminWhen: [
      '学校作息、教学周或教室字典本身配置错误，导致大面积正常任务无法排课。',
      '同一教师/班级/教室出现无法通过现有课表项解释的历史冲突，需要修复旧数据。',
      '已发布课表存在正式事实错误且普通调停课无法修复，需要走受控作废重发。'
    ],
    related: [
      { label: '排课管理', route: '/admin/academic-affairs/scheduling' },
      { label: '课表发布', route: '/admin/academic-affairs/schedule/publish' },
      { label: '选课管理', route: '/admin/academic-affairs/selection' }
    ]
  },
  {
    id: 'aa-v3-credit-gpa',
    module: '教务中心 · 学分与绩点',
    title: '学分和 GPA 从哪里来，补考重修后为什么会变化',
    roles: ['教务人员', '学院管理员', '任课教师', '学校管理员'],
    route: '/admin/academic-affairs/transcript',
    entry: '教务中心 → 成绩管理 → 学生成绩单；学业预警控制台可查看学分/绩点风险',
    keywords: ['学分', 'GPA', '绩点', '有效成绩', 'earnedCredits', 'AcademicStudent', '补考', '重修', '毕业资格'],
    summary: '学分和 GPA 来自正式有效成绩，不直接对所有历史成绩行求和。同一课程存在正常考试、补考、重修、更正等多条正式记录时先按有效成绩策略收敛；已通过有效成绩贡献学分，GPA 再按当前课程绩点规则计算并写入 AcademicStudent 学业台账。',
    prerequisites: [
      '课程成绩已经正式发布，或者补考/重修等后续成绩已按对应正式流程回写。',
      '成绩记录应具备稳定课程身份、学分和有效成绩策略所需来源信息；历史身份缺失数据可能需要先治理。',
      '学生需要有 AcademicStudent 学业过程台账；无台账时部分汇总只能返回“无学业记录”。'
    ],
    permissions: [
      '成绩单和学业汇总的可见范围仍由 academicAffairs.grade.view 及当前角色数据范围控制。',
      'GPA/学分是服务端正式投影，不允许通过前端显示值手工改写；成绩变化必须来自成绩发布、更正、补考/重修等正式业务链。'
    ],
    steps: [
      '在学生成绩单/学业汇总中查看正式课程成绩、earnedCredits、gpa 和 failCount。',
      '系统先按稳定课程身份和有效成绩策略收敛同一课程的多条正式成绩，避免补考/重修与原成绩被重复计学分。',
      '有效成绩中通过的课程按 credit_value 累计已获学分；毕业资格审核也使用收敛后的有效通过成绩核算，不直接裸 SUM 全部历史成绩行。',
      '当前百分制课程绩点规则为：成绩低于 60 绩点为 0；60 分及以上按 (成绩-50)/10 映射，60→1.0、100→5.0。',
      '存在有效学分时，GPA 按“课程绩点×课程学分”的加权平均计算并保留两位；如果有效成绩总学分为 0，则按现有服务规则退化为课程绩点简单平均。',
      '补考/重修/成绩更正形成新的有效正式结果后，学业台账会随正式成绩链刷新，后续学分预警、绩点预警和毕业资格审核读取更新后的投影。'
    ],
    warnings: [
      '当前绩点映射是项目现行规则，代码注释明确学校自定义绩点档位尚未参数化；帮助不能承诺“每校可自由配置 GPA 算法”。',
      '不要把多条 ACTIVE 成绩直接相加学分；同一课程的补考/重修正式行并存是正常历史事实。',
      '毕业资格的学分判断以学生确定培养方案的毕业总学分为目标，不是只看页面某个累计数字。'
    ],
    successCriteria: [
      '学生成绩单汇总能返回与有效正式成绩一致的 earnedCredits、gpa 和 failCount。',
      '补考通过、重修通过或正式成绩更正后，不会把同一门课学分重复累计。',
      '毕业资格审核中的 CREDIT 证据与学生适用培养方案和有效成绩口径一致。'
    ],
    nextSteps: [
      '仍有未通过课程时进入「补考重修缓考免修」处理；完成后再核对有效成绩、学分和 GPA。',
      '毕业年级在学分、必修/选修和实践要求收口后，进入「毕业资格审核工作台」做跨域预审。'
    ],
    troubleshooting: [
      '学分与预期不一致：先核对课程是否通过、credit_value 是否正确，以及同一课程是否存在补考/重修/更正后的有效结果。',
      'GPA 与手工计算不一致：确认使用的是当前项目 60→1.0、100→5.0 规则，并按课程学分加权，不要套用其他学校绩点档位。',
      '补考通过后仍显示挂科：检查有效成绩策略是否已选到补考/后续正式成绩，避免只看原始 FAILED 行。',
      '毕业审核显示 CREDIT UNKNOWN：检查学生适用培养方案是否唯一可解析、方案是否设置毕业总学分、学业台账是否存在。'
    ],
    contactAdminWhen: [
      '学校制度要求另一套 GPA 映射或特殊课程不计绩点，而当前规则中心尚未支持该制度。',
      '历史成绩缺少稳定课程身份/学分，导致有效成绩无法可靠收敛。',
      '正式成绩已正确发布但 AcademicStudent 学业投影长期未刷新，需要排查投影数据。'
    ],
    related: [
      { label: '学生成绩单', route: '/admin/academic-affairs/transcript' },
      { label: '学业预警', route: '/admin/academic-affairs/warnings/console' },
      { label: '补考重修', route: '/admin/academic-affairs/makeup' },
      { label: '毕业资格审核', route: '/admin/academic-affairs/graduation/audit-console' }
    ]
  },
  {
    id: 'aa-v3-makeup-retake',
    module: '教务中心 · 补考重修',
    title: '挂科以后如何走补考、重修并回写正式成绩',
    roles: ['教务人员', '学院管理员', '学生', '学校管理员'],
    route: '/admin/academic-affairs/makeup',
    entry: '教务中心 → 补考重修缓考免修；学生申请从本人重修免修入口进入',
    keywords: ['补考', '重修', '缓考', '免修', 'MAKEUP', 'REVIEWED', 'FINISHED', 'CAP60', '正式成绩回写'],
    summary: '补考候选来自成绩发布后的正式不及格记录。补考批次经名单/考务编排后发布，录分后必须全部完成学院审核，再由教务发布回写新的正式成绩来源；重修和免修是独立申请链，不能用手工改原成绩代替。',
    prerequisites: [
      '原课程成绩已经正式发布并形成有效不及格记录；没有正式成绩来源时不要人为创建“补考事实”。',
      '补考批次由教务处建立，所需考场/监考可关联真实考务批次；缓考合流只读取已批准的缓考记录。',
      '重修/免修申请需满足当前规则中心次数上限、成绩/学期条件等服务端校验。'
    ],
    permissions: [
      '补考批次管理使用 academicAffairs.makeup.manage，列表查看使用 academicAffairs.makeup.view；服务层对学校级补考关键写操作要求 TENANT_ALL 教务处范围。',
      '学生重修申请使用 academicAffairs.retake.apply，审核使用 retake.review；免修审核使用 academicAffairs.exemption.review。',
      '不能通过成绩页面直接覆盖原挂科成绩来替代补考/重修正式流程。'
    ],
    steps: [
      '从正式挂科候选中建立/圈定补考名单，创建补考批次。DRAFT/ARRANGED 阶段可以纳入名单并关联考务批次。',
      '完成考务安排后将 ARRANGED 补考批次发布为 PUBLISHED，随后才允许录入补考成绩；首次录分后批次进入 SCORING。',
      '全部补考记录都必须为 SCORED 后才能提交学院审核，批次进入 REVIEWED。',
      '教务对 REVIEWED 批次执行最终发布回写。系统按当前补考计分规则生成/更新 source=MAKEUP（清考为 CLEARANCE）的正式成绩，并带出原课程真实学分，最终批次进入 FINISHED。',
      '学生需要重修时走重修申请和教务审批，再进入跟班/后续教学；免修则走任课教师→学院→教务处的独立审核链。',
      '回到学生成绩单/学业汇总核对新的有效成绩、学分、GPA 和挂科状态，再继续毕业资格检查。'
    ],
    warnings: [
      '补考成绩不是录完就生效；必须经过学院审核和教务发布回写。',
      '当前补考计分规则默认从规则中心读取，缺省 CAP60；不要把“及格就永远记 60”写成不可配置制度。',
      '原挂科成绩和补考/重修正式成绩可以并存，学业统计必须经过有效成绩策略收敛，不能把历史行当脏数据直接删除。'
    ],
    successCriteria: [
      '补考批次完成 PUBLISHED → SCORING → REVIEWED → FINISHED，并形成可追溯的正式成绩来源。',
      '补考通过后有效成绩、学分与挂科结论按正式策略更新，不重复计算同一课程学分。',
      '重修/免修等申请保留各自审批状态和审计，不通过手工改分绕过。'
    ],
    nextSteps: [
      '处理完未通过课程后重新查看学分/GPA和毕业风险，确认培养方案要求是否已经达标。',
      '毕业年级所有补考重修结果正式回写后，再进入毕业资格终审，避免用未完成补考的临时分数判毕业。'
    ],
    troubleshooting: [
      '补考批次无法发布：确认状态已到 ARRANGED，并已完成当前学校要求的名单/考务准备。',
      '学院审核被阻断：检查是否仍有补考记录未 SCORED。',
      '教务发布被阻断：批次必须先 REVIEWED，不能从 SCORING 直接回写正式成绩。',
      '补考通过但学分没更新：检查回写成绩是否带出原课程 credit_value，以及有效成绩策略是否已经选中后续成绩。'
    ],
    contactAdminWhen: [
      '原正式成绩缺少课程学分/稳定课程身份，导致补考回写无法继承正确学分。',
      '学校补考/重修计分制度与当前规则中心能力不一致，需要先配置或开发制度规则。',
      '学生明明符合申请条件但被次数/数据范围异常阻断，且规则配置与历史记录都无法解释。'
    ],
    related: [
      { label: '补考重修控制台', route: '/admin/academic-affairs/makeup' },
      { label: '学生重修免修申请', route: '/admin/academic-affairs/my-makeup' },
      { label: '学生成绩单', route: '/admin/academic-affairs/transcript' }
    ]
  },
  {
    id: 'aa-v3-graduation-qualification',
    module: '教务中心 · 毕业资格',
    title: '毕业资格如何预审、为什么 UNKNOWN 不能直接判通过',
    roles: ['教务人员', '学院管理员', '学校管理员'],
    route: '/admin/academic-affairs/graduation/audit-console',
    entry: '教务中心 → 毕业资格预审 / 毕业资格审核工作台',
    keywords: ['毕业资格', '毕业预审', '学分审核', '必修', '选修', '实践', '实习', '毕业设计', '处分', 'UNKNOWN', 'GRADUATED'],
    summary: '毕业资格不是只看总学分。系统先唯一解析学生适用培养方案，再对学籍、总学分、必修、选修、实践、岗位实习、毕业设计、处分等核心项做 PASS/FAIL/UNKNOWN 三态检查；关键项 UNKNOWN 会进入异常队列，不能被当成 PASS。',
    prerequisites: [
      '毕业年级学生的学籍、培养方案绑定、正式成绩、补考重修结果应先收口；适用培养方案必须能唯一解析。',
      '岗位实习、毕业设计、学工处分等跨域正式结果应已经形成可查询记录。',
      '不要在补考重修尚未正式回写、培养方案绑定仍歧义时提前把毕业预审结果当最终结论。'
    ],
    permissions: [
      '毕业资格查看使用 academicAffairs.graduation.view；批次管理/预审/归档使用 graduation.manage；学院初审和教务终审分别使用 graduation.collegeReview / graduation.final。',
      '建批次、预审、终审、归档等高风险动作在 service 内还有角色白名单，权限码通过后仍可能因角色不符被拒绝。'
    ],
    steps: [
      '建立毕业审核批次并圈定毕业年级学生，运行系统预审。重复生成/预审按当前服务逻辑幂等更新结果，不靠追加重复行制造多个真值。',
      '系统先按班级特例、专业和年级解析唯一适用培养方案；方案缺失或歧义时，学分/选修/实践等关键项返回 UNKNOWN。',
      '逐项查看 STATUS、CREDIT、COURSE_REQUIRED、COURSE_ELECTIVE、PRACTICE、INTERNSHIP、GRADUATION_DESIGN、DISCIPLINE 等核心证据。有效学分按正式有效成绩收敛后计算，避免同一课程重复学分。',
      '对 FAIL 项回到对应业务域处理；对 UNKNOWN 项先修复“无法证明”的数据来源，不能人工把 UNKNOWN 理解成系统通过。',
      '学院完成初审后由教务终审。终审结论通过统一学籍状态变更入口写入 GRADUATED / COMPLETED / INCOMPLETE 等正式主档状态，并要求受控确认。',
      '归档只收敛已经终审完成的正式结果；终审前不要把预审页面当作最终毕业名单。'
    ],
    warnings: [
      'UNKNOWN 表示系统缺少足够证据，不等于 PASS；关键学业/培养过程项 UNKNOWN 会阻断自动通过。',
      '总学分达标不代表毕业资格一定通过，必修、选修、实践、实习、毕设、处分等仍需分别核验。',
      '毕业资格会重新解析学生适用培养方案，不允许简单取“第一条 ACTIVE 方案”猜测。'
    ],
    successCriteria: [
      '每名学生关键审核项都有可解释的 PASS/FAIL/UNKNOWN 和证据来源。',
      '所有阻断 FAIL/UNKNOWN 已处理或按学校制度形成明确人工结论，学院初审和教务终审均完成。',
      '终审结果通过统一学籍状态入口写回学生主档，归档仅包含已终审正式结果。'
    ],
    nextSteps: [
      '终审通过后按学校流程进入毕业证/结业证管理、离校及最终教务归档。',
      '对未通过或延期学生保留具体未达标证据，后续补修完成后再按正式规则复核，不手工删除历史阻断记录。'
    ],
    troubleshooting: [
      'CREDIT UNKNOWN：检查适用培养方案是否唯一、是否设置毕业总学分，以及学生是否有学业台账。',
      '必修/选修/实践 UNKNOWN：检查方案课程模块、requirement_json 和正式成绩是否齐全。',
      '补考已经通过但仍显示必修失败：检查有效成绩收敛结果，不要直接扫描原始 FAILED 历史行。',
      '实习/毕设/处分显示 UNKNOWN：回到对应业务域确认是否存在正式可追溯记录，不要在毕业页凭口头结果改状态。'
    ],
    contactAdminWhen: [
      '同一学生适用培养方案存在歧义，普通业务人员无法通过方案绑定页面消除。',
      '跨域正式结果已经存在，但毕业预审仍无法读取，需要排查供数关系。',
      '终审结论与主档状态写回不一致，属于高风险正式事实问题，应停止继续归档并由管理员核查。'
    ],
    related: [
      { label: '毕业资格预审', route: '/admin/academic-affairs/graduation' },
      { label: '毕业资格审核工作台', route: '/admin/academic-affairs/graduation/audit-console' },
      { label: '毕业证书管理', route: '/admin/academic-affairs/certificates' }
    ]
  }
]
