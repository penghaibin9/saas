/**
 * 教务中心 · 知识清洗 V2 正式任务卡。
 *
 * 只保留已经按当前路由、服务层、权限/数据范围和状态机重新核验的高频任务。
 * 历史 helpContent 中未进入本文件的教务卡继续由 verified-only 门隔离，不因“尚未证明错误”继续发布。
 */
export const ACADEMIC_AFFAIRS_CLEAN_HELP_CARDS = [
  {
    id: 'aa-card-status-change',
    module: '教务中心 · 学籍异动',
    title: '休学、复学、退学、转专业、转班等学籍异动如何办理',
    roles: ['辅导员', '教务人员', '学校管理员'],
    route: '/admin/academic-affairs/status-changes',
    entry: '教务中心 → 学籍异动',
    keywords: ['学籍异动', '休学', '复学', '退学', '转专业', '转班', '保留学籍', '留级', '异动审批'],
    summary: '学籍异动按真实 changeType 进入对应审批链，终审才通过统一学籍状态变更入口生效；同一学生存在在途异动时会被阻断，审批权限同时受权限码和数据范围约束。',
    prerequisites: [
      '先从学生主档确认当前学籍状态、学院/专业/班级和拟办理异动类型。',
      '转专业、转班等涉及目标组织的异动，应先确认目标专业/班级真实存在且满足服务端校验。',
      '休学期限按规则中心 suspendMaxYears 校验；当前代码默认值为 2 年，但学校有效配置可以改变上限，不能把“2 年”写成固定制度。'
    ],
    permissions: [
      '辅导员初审要求 academicAffairs.statusChange.counselorReview，并按本人班级数据范围收敛。',
      '学院节点要求 academicAffairs.statusChange.collegeReview，并按原学院或转专业目标学院的数据范围收敛。',
      '教务处终审要求 academicAffairs.statusChange.officeReview，且仅 TENANT_ALL 的教务处/校管范围可执行。'
    ],
    steps: [
      '进入「学籍异动」，按实际业务选择休学 SUSPEND、复学 RESUME、退学 WITHDRAW、转专业 TRANSFER_MAJOR、转班 TRANSFER_CLASS、保留学籍 PRESERVE 或留级 RETAIN。',
      '填写异动原因和页面要求的目标专业、目标班级、有效/到期日期等真实字段；不要用前端传参替代服务端对目标组织和期限的校验。',
      '提交后系统按异动类型生成真实审批节点。休学/退学/保留学籍/转班为辅导员→学院→教务处；复学包含学院分班；转专业还包含转出学院和转入学院；留级为学院→教务处。',
      '各节点审批人按当前待办和数据范围办理；无对应权限码或不在数据范围内时后端拒绝，而不是靠页面是否显示按钮判断权限。',
      '只有教务处终审通过后才调用统一学籍状态变更入口生效；转专业、复学等需要同步主档组织关系的业务在终审中按服务端规则处理。',
      '异动完成后回到异动详情和学生主档核对最终状态、组织归属、审批轨迹和生效日期。'
    ],
    warnings: [
      '同一学生已有 DRAFT / SUBMITTED / IN_REVIEW 在途异动时，不要重复发起第二条在途异动。',
      '不要把旧帮助中的“休学默认 2 年”理解为固定期限；真实约束来自学校当前生效的 suspendMaxYears。',
      '保留学籍 PRESERVE 与留级 RETAIN 是两个独立异动类型，不能混用。'
    ],
    successCriteria: [
      '异动实例进入正确审批链，当前节点与办理角色一致。',
      '终审通过后学生主档显示正确的新学籍状态；涉及专业/班级调整时组织归属同步正确。',
      '异动详情保留申请、审批节点、最终结果和审计轨迹。'
    ],
    troubleshooting: [
      '提示 409 已有在途异动：先处理或终结现有 DRAFT / SUBMITTED / IN_REVIEW 记录，不重复新建。',
      '审批按钮不可用或 403：检查当前节点所需 permissionCode，以及账号的学院/班级/TENANT_ALL 数据范围。',
      '休学或复学期限校验失败：核对当前学校规则中心的休学最长年限和原休学到期信息。',
      '转专业/转班提交失败：核对目标专业/班级是否符合服务端关系校验，不要仅修改前端显示值。'
    ],
    related: [
      { label: '发起异动', route: '/admin/academic-affairs/status-changes/new' },
      { label: '异动审批', route: '/admin/academic-affairs/status-changes/approval' },
      { label: '异动生效', route: '/admin/academic-affairs/status-changes/effective' }
    ]
  },
  {
    id: 'aa-card-grade-entry',
    module: '教务中心 · 成绩管理',
    title: '教师如何录入并提交课程成绩',
    roles: ['任课教师', '教务人员'],
    route: '/admin/academic-affairs/grade-entry',
    entry: '教务中心 → 成绩管理 → 成绩录入',
    keywords: ['成绩录入', '动态成绩项', '权重', '特殊状态', '缺考', '缓考', '免考', '作弊', '提交成绩'],
    summary: '成绩方案支持 1–12 个动态成绩项且权重必须严格合计 100；首次正式录分后方案锁定。任务仅在 NOT_STARTED / INPUTTING / RETURNED 可编辑，特殊状态不是普通 0 分。',
    prerequisites: [
      '当前成绩任务必须属于本人授课或当前账号允许办理的数据范围，并处于 NOT_STARTED、INPUTTING 或 RETURNED。',
      '先确认课程当前有效成绩方案；动态方案存在时以动态成绩项为准，只有没有动态方案时才使用旧比例兼容口径。',
      '提交前确认正式教学名单已经收口，正常成绩没有遗漏。'
    ],
    permissions: [
      '教师录分只能在本人真实教学关系/允许数据范围内办理；教务角色的管理能力仍以后端权限和数据范围为准。',
      '提交后的成绩任务进入审核链并只读，只有正式退回到 RETURNED 后才能再次修改。'
    ],
    steps: [
      '进入「成绩录入」选择本人当前可办理的课程成绩任务。',
      '核对当前成绩方案。动态方案允许 1–12 个成绩项，所有权重必须严格合计 100。',
      '逐学生录入成绩。NORMAL 按各成绩项计算；ABSENT、DEFERRED、EXEMPT、CHEAT 等特殊状态按独立状态保存，不要用 0 分冒充特殊状态。',
      '首次正式写入成绩后方案会锁定；如发现方案本身错误，不要继续录分后再试图改权重，应先按系统允许的配置流程处理。',
      '提交前处理缺项和名单差异并通过服务端质量校验；可选成绩项没有提交时按当前计算规则计入 0 分。',
      '确认无误后提交。提交后任务进入审核状态并冻结当次正式教学名单快照。'
    ],
    warnings: [
      '不要继续使用旧帮助中的“总评固定等于平时分×比例 + 期末分×比例”作为统一规则。',
      '特殊状态不是普通 0 分；错误地把缺考/缓考/免考/作弊写成 0 分会改变正式成绩语义。',
      '提交后不能靠前端重新打开页面绕过只读状态。'
    ],
    successCriteria: [
      '成绩任务不存在正常学生缺项或名单外记录，服务端质量校验通过。',
      '提交后任务进入正式审核链，并保存本次正式名单快照。',
      '再次打开任务时，非 RETURNED 状态不会允许继续改分。'
    ],
    troubleshooting: [
      '提示权重不为 100：回到有效成绩方案核对所有动态成绩项，不要在学生成绩行临时修正公式。',
      '提示名单变化或存在名单外成绩：按最新正式教学名单收口后重新提交。',
      '提交后发现录错：不要尝试覆盖已提交/已发布成绩；审核阶段等待正式退回，已发布后走成绩更正。'
    ],
    related: [
      { label: '成绩审核', route: '/admin/academic-affairs/grade-review' },
      { label: '成绩发布', route: '/admin/academic-affairs/grade-publish' },
      { label: '成绩更正', route: '/admin/academic-affairs/grade-change' }
    ]
  },
  {
    id: 'aa-card-grade-review-publish',
    module: '教务中心 · 成绩管理',
    title: '课程成绩如何审核并正式发布',
    roles: ['教务人员', '学校管理员'],
    route: '/admin/academic-affairs/grade-review',
    entry: '教务中心 → 成绩管理 → 成绩审核 / 成绩发布',
    keywords: ['成绩审核', '学院审核', '教务终审', '成绩发布', 'PUBLISHED', '名单快照', '学业预警'],
    summary: '教师提交后先冻结正式教学名单快照，再经学院审核和教务终审。正式发布事务生成 AcademicGrade 正式投影并刷新学业聚合；全量学业预警扫描在事务提交后独立执行，扫描失败不会回滚已经发布的成绩。',
    prerequisites: [
      '成绩任务已经由教师正式提交，正常成绩无缺项且提交时正式名单快照已生成。',
      '学院审核和教务终审应按当前节点、权限码及数据范围办理。',
      '发布前必须保证冻结名单仍与当前教学班正式名单一致。'
    ],
    permissions: [
      '学院审核仅能处理本学院数据范围内的任务；教务终审/正式发布要求对应教务权限。',
      '管理员特殊补录不能借普通教学任务发布入口绕过正式审批链。'
    ],
    steps: [
      '学院审核提交后的成绩任务；需要教师修改时按真实退回动作把任务退回 RETURNED。',
      '学院通过后任务进入 ACADEMIC_REVIEW，由教务终审角色继续处理。',
      '正式发布前重新校验冻结名单、正常成绩完整性和名单外记录；任何阻断项未收口都不能发布。',
      '发布事务将任务置为 PUBLISHED，为每条成绩生成正式 AcademicGrade 投影，冻结课程身份、修读次数、教学班/名单版本和有效成绩策略快照，并刷新学生学业聚合。',
      '不及格记录在发布事务内生成对应风险；事务提交成功后再触发全量学业预警扫描。',
      '查看 warningScanOk / warningScanError 判断后置扫描结果。扫描失败时单独排查预警链，不要再次发布已经 PUBLISHED 的成绩。'
    ],
    warnings: [
      '成绩“发布成功”和“全量预警扫描成功”是两个结果，不能写成一个原子终态。',
      '不要直接覆盖已发布正式成绩；需要改分时走成绩更正，保留版本和审批留痕。'
    ],
    successCriteria: [
      '任务状态为 PUBLISHED，并形成正式 AcademicGrade 投影和最新学业聚合。',
      '发布前使用的正式名单/成绩策略快照可追溯。',
      '后置预警扫描成功则 warningScanOk 为真；失败时成绩仍保持已发布并有可排查错误信息。'
    ],
    troubleshooting: [
      '发布前提示名单变化：回到正确教学名单/成绩流程重新收口，不能继续用旧快照发布。',
      '发布后 warningScanOk=false：成绩已经正式发布，不要重复点发布；单独排查学业预警扫描。',
      '重复发布被拒绝：确认任务已 PUBLISHED，后续纠错走成绩更正而不是重复发布。'
    ],
    related: [
      { label: '成绩发布', route: '/admin/academic-affairs/grade-publish' },
      { label: '成绩更正', route: '/admin/academic-affairs/grade-change' },
      { label: '学业预警', route: '/admin/academic-affairs/warnings' }
    ]
  },
  {
    id: 'aa-card-grade-change',
    module: '教务中心 · 成绩管理',
    title: '已发布成绩发现错误后如何更正',
    roles: ['任课教师', '教务人员', '学校管理员'],
    route: '/admin/academic-affairs/grade-change',
    entry: '教务中心 → 成绩管理 → 成绩更正',
    keywords: ['成绩更正', '改分', '已发布成绩', 'PENDING_COLLEGE', 'PENDING_ACADEMIC', 'SUPERSEDED', '版本链'],
    summary: '只有已发布成绩可以发起正式更正。发起时只创建更正请求，不覆盖当前正式成绩；学院和教务终审通过后才追加新的 AcademicGrade 版本，旧版本转为 SUPERSEDED。',
    prerequisites: [
      '目标成绩任务必须已经 PUBLISHED；未发布成绩应回原录入/审核流程处理。',
      '更正原因必填且不少于 5 个字，并准备可追溯的更正依据。',
      '同一成绩存在在途更正请求时先处理当前请求，不重复并发发起。'
    ],
    permissions: [
      '发起人必须满足真实教学关系/成绩更正权限和数据范围；审批节点要求 academicAffairs.gradeChange.review 等服务端权限。',
      '学院和教务终审均会重新校验当前任务、正式成绩版本及并发版本，不能依赖前端缓存强行覆盖。'
    ],
    steps: [
      '进入「成绩更正」定位已发布的目标成绩，填写拟更正值、至少 5 字原因和页面要求的依据。',
      '提交后系统创建更正请求；审批期间当前正式成绩保持不变，成绩单和其他正式业务继续读取当前 ACTIVE 版本。',
      '学院节点审核后进入教务终审；驳回必须填写不少于 5 字原因，并结束本次更正，不改变正式成绩。',
      '教务终审批准时锁定更正请求和当前 ACTIVE 成绩，校验版本无漂移后，在同一事务中追加新的 AcademicGrade。',
      '原正式成绩版本转为 SUPERSEDED，新版本成为当前 ACTIVE；连续更正形成可追溯版本链，而不是原地覆盖。',
      '完成后重新核对成绩详情、学生聚合以及更正审批/版本轨迹。'
    ],
    warnings: [
      '不要直接编辑数据库或覆盖原正式成绩行；正式更正必须形成追加式版本链。',
      '并发终审或版本变化可能返回 409，应刷新后按最新正式版本处理，不重复强提交。'
    ],
    successCriteria: [
      '终审批准后存在新的 ACTIVE 正式成绩版本，旧版本保留且标记为 SUPERSEDED。',
      '成绩更正请求、审批动作、更正原因和版本变化可追溯。',
      '被驳回的更正不会改变当前正式成绩。'
    ],
    troubleshooting: [
      '提示“仅已发布成绩可申请更正”：回到成绩任务确认是否真正 PUBLISHED。',
      '提示原因不足：补充不少于 5 字的真实更正理由。',
      '出现 409 版本/并发冲突：刷新当前 ACTIVE 成绩和请求状态，再决定是否重新发起，不强行覆盖。'
    ],
    related: [
      { label: '成绩录入', route: '/admin/academic-affairs/grade-entry' },
      { label: '成绩审核', route: '/admin/academic-affairs/grade-review' },
      { label: '成绩发布', route: '/admin/academic-affairs/grade-publish' }
    ]
  },
  {
    id: 'aa-card-selection-round',
    module: '教务中心 · 选课管理',
    title: '如何配置并运行多轮次选课',
    roles: ['教务人员', '学校管理员'],
    route: '/admin/academic-affairs/selection',
    entry: '教务中心 → 选课管理',
    keywords: ['选课轮次', '预选', '正选', '补退选', 'FCFS', 'LOTTERY', '抽签', '摇号', '可选可退'],
    summary: '选课支持无轮次的先到先得兼容模式，也支持 FCFS / LOTTERY 多轮次；同一批次同时只能有一个 OPEN 轮次，抽签轮次必须先关闭后才能摇号且只能摇一次。',
    prerequisites: [
      '先创建并发布真实选课批次，且批次当前处于允许开启轮次的 OPEN 状态。',
      '确认课程供给、容量、开班下限和学生可选范围已经按学校规则配置。',
      '决定本轮是 FCFS 先到先得还是 LOTTERY 抽签，并明确 allowEnroll / allowDrop。'
    ],
    permissions: [
      '轮次创建、开启、关闭和摇号要求选课管理范围；服务端通过 _require_manage_scope 再次校验，不以页面按钮为准。',
      '学生最终可选范围还会由服务端校验学籍、课程资格、冲突、容量和当前轮次动作权限。'
    ],
    steps: [
      '进入「选课管理」选择目标批次并创建轮次，填写轮次名称，选择 FCFS 或 LOTTERY，并配置是否允许选课/退课。',
      '轮次初始为 DRAFT。批次处于 OPEN 后开启轮次；如果同批次已有另一个 OPEN 轮次，系统会 409 阻止同时开启。',
      'FCFS 轮次由学生按服务器事务直接占用容量；LOTTERY 轮次的学生申请先进入 PENDING，不在前端直接宣布中签。',
      '轮次结束后执行关闭，状态由 OPEN 进入 CLOSED。',
      'LOTTERY 轮次只有 CLOSED 状态才能摇号；摇号执行时原子抢占状态并进入 DRAWN，已摇过的轮次不能重摇。',
      '摇号按课程剩余容量产生中签/落签结果；容量在关轮后发生外部变化时不会硬塞超容学生，而是按当前真实容量处理。'
    ],
    warnings: [
      '页面显示的剩余名额只是读取时快照，最终能否选中以服务端锁定后的容量和资格校验为准。',
      '不要把 LOTTERY 写成不可复核的“随机黑盒”；当前实现按记录和轮次派生确定性顺序，可重复核验。',
      '当前只真实实现 FCFS 和 LOTTERY；志愿抽签/投积分等未实现模式不能写入正式帮助。'
    ],
    successCriteria: [
      '同一批次任一时刻最多一个 OPEN 轮次。',
      'LOTTERY 轮次关闭后摇号一次进入 DRAWN，中签记录为 SELECTED、未中签为 LOTTERY_LOST。',
      '任何选课/摇号结果都不突破课程真实容量。'
    ],
    troubleshooting: [
      '开启轮次提示已有 OPEN 轮次：先关闭当前开放轮次，再开启下一轮。',
      '摇号提示不可执行：确认轮次为 LOTTERY 且已 CLOSED；DRAWN 终态不能重复摇。',
      '学生看到有余量却选不上：检查服务端返回的资格、时间冲突、容量并发或当前轮次 allowEnroll，而不是只看页面名额。'
    ]
  },
  {
    id: 'aa-card-selection-publish',
    module: '教务中心 · 选课管理',
    title: '选课批次发布前后要检查什么',
    roles: ['教务人员', '学校管理员'],
    route: '/admin/academic-affairs/selection',
    entry: '教务中心 → 选课管理 → 批次与课程供给',
    keywords: ['选课批次', '发布选课', 'DRAFT', 'PUBLISHED', '课程容量', '开班下限', '退课', '补选'],
    summary: '只有 DRAFT 选课批次可以发布；发布时后端加锁并要求至少存在一门有效可选课程，同时校验容量和开班下限。学生选课/退课最终以服务器事务和当前批次、轮次状态为准。',
    prerequisites: [
      '批次仍为 DRAFT，尚未锁定或归档。',
      '至少配置一门状态为 OPEN 的有效可选课程。',
      '每门课程 capacity 必须大于 0，minCapacity 不能小于 0 且不能大于 capacity。'
    ],
    permissions: [
      '批次发布要求选课管理范围，后端在加锁读取批次后再次执行管理范围校验。',
      '学生选课只操作本人记录；退课和关闭后的补选资格由后端真实记录决定，不能信任前端自报标志。'
    ],
    steps: [
      '在「选课管理」完成批次和课程供给配置，逐门核对课程状态、容量和开班下限。',
      '执行发布。后端对批次行加锁，只接受 DRAFT 状态，并重新读取有效 OPEN 课程。',
      '如果没有有效课程，或 capacity / minCapacity 配置非法，发布会直接阻断，不生成“看起来已发布”的半成品批次。',
      '发布完成后再按学校方案开启选课窗口/轮次。学生选课时后端锁定课程和批次，重新校验学籍、资格、冲突和容量。',
      '学生退课必须处于允许退课的 OPEN 窗口/轮次；已选容量计数在同一事务中守护扣减。',
      '关闭批次后的特殊补选只认可本人真实 COURSE_CANCELLED 记录等服务端资格，不使用前端参数绕过。'
    ],
    warnings: [
      '不要把前端当前筛选或容量数字当成最终选课事实，正式结果以后端事务记录为准。',
      '不要宣传“关闭后任何学生都能补选”；当前代码只在满足真实补选资格时开放。'
    ],
    successCriteria: [
      '发布成功的批次来自 DRAFT 且至少有一门有效可选课程，课程容量规则全部通过服务端校验。',
      '学生选课、退课与课程 selectedCount 在并发情况下保持一致，不出现超容。',
      '关闭后的补选没有绕过真实 COURSE_CANCELLED 等资格记录。'
    ],
    troubleshooting: [
      '发布提示无有效课程：检查课程是否为 OPEN，并确认不是已取消/删除供给。',
      '提示容量或开班下限无效：修正 capacity / minCapacity 后再发布。',
      '学生选课 409：按返回原因检查容量、资格、冲突、批次/轮次状态，刷新服务器真值后再处理。'
    ],
    related: [
      { label: '选课归档', route: '/admin/academic-affairs/selection/archive' }
    ]
  },
  {
    id: 'aa-card-exam-arrangement',
    module: '教务中心 · 考务管理',
    title: '考试批次如何完成课程确认与排考',
    roles: ['教务人员', '学校管理员'],
    route: '/admin/academic-affairs/exam',
    entry: '教务中心 → 考务管理',
    keywords: ['考务', '考试批次', 'COURSE_CONFIRMED', '自动排考', '考场', '座位', '监考', '冲突检测'],
    summary: '考试批次按 DRAFT → COURSE_CONFIRMED → ARRANGED → PUBLISHED → FINISHED → ARCHIVED 流转。课程确认后可人工编排，也有真实自动排考引擎；自动排考只在 COURSE_CONFIRMED 阶段运行，并如实返回未排原因，不覆盖人工考场。',
    prerequisites: [
      '由教务处创建考试批次并在 DRAFT 阶段圈定真实教学任务对应的考试课程。',
      '所有有效考试课程先完成学院确认；存在未确认课程时不能把批次推进到 COURSE_CONFIRMED。',
      '自动排考前应准备考试时间网格、可用教室、在读学生花名册和监考教师池；缺失资源会形成漏排原因。'
    ],
    permissions: [
      '创建批次、批次课程确认推进和自动排考只允许教务处/TENANT_ALL；学院教务对课程操作按 college_id 数据范围收敛。',
      '人工考场、监考等写操作仍会校验当前批次状态和学院范围，ARCHIVED 批次统一只读。'
    ],
    steps: [
      '进入「考务管理」创建 DRAFT 考试批次并从真实教学任务圈定考试课程。',
      '学院在本学院范围内确认或移除待确认课程；所有有效课程均 CONFIRMED 后，由教务处推进批次到 COURSE_CONFIRMED。',
      '按需要设置考试日期、开始/结束时间和时长。人工编排时添加考场、铺座位并安排监考；同教师同时段监考冲突会被 409 拒绝。',
      '需要自动排考时，在 COURSE_CONFIRMED 阶段执行。自动流程可以先自动定时，再切分考场、铺座位和分配监考。',
      '自动排考只增量处理没有 ACTIVE 考场的课程；已有人工/既有考场的课程整体跳过，不重复覆盖。',
      '时间未定、无花名册、无可用教室或总容量不足时，自动排考返回 NO_TIME / NO_ROSTER / NO_ROOM / ROOM_SHORT 等真实漏排原因，先处理根因再重跑。'
    ],
    warnings: [
      '旧帮助如果写“系统没有自动排考”已经失真；当前后端存在真实自动定时、考场切分、座位和监考编排。',
      '也不能把自动排考宣传成无条件成功：资源不足时必须保留漏排，不会硬塞考生或制造冲突。',
      '自动清除/重排只针对 source=AUTO 的结果，人工编排不应被自动流程覆盖。'
    ],
    successCriteria: [
      '考试批次已进入 COURSE_CONFIRMED，所有有效考试课程均已确认。',
      '计划发布的课程都有真实考试时间、考场、座位和监考安排，自动排考漏项已逐项处理。',
      '监考/巡考不存在同教师同一时段冲突，考场容量能够覆盖实际安排。'
    ],
    troubleshooting: [
      '批次无法推进 COURSE_CONFIRMED：检查是否仍有 PENDING_CONFIRM 的有效考试课程。',
      '自动排考提示阶段错误：只在 COURSE_CONFIRMED 阶段执行，不在已发布/归档批次上重排。',
      '出现 NO_TIME / NO_ROSTER / NO_ROOM / ROOM_SHORT：按具体根因补时间、花名册、教室资源或容量，不把漏排当成功。',
      '监考分配 409：检查该教师同一时段已有监考或巡考任务。'
    ]
  },
  {
    id: 'aa-card-exam-publish',
    module: '教务中心 · 考务管理',
    title: '考试安排满足什么条件才能正式发布',
    roles: ['教务人员', '学校管理员'],
    route: '/admin/academic-affairs/exam',
    entry: '教务中心 → 考务管理 → 发布考试安排',
    keywords: ['考试发布', 'ARRANGED', 'PUBLISHED', '考场', '座位', '监考', '考试通知', '归档'],
    summary: '考试发布只接受 COURSE_CONFIRMED / ARRANGED 批次，并在发布前逐门检查每个已确认考试课程至少有考场、座位和监考；任何缺项都会 409 阻止发布，成功后才进入 PUBLISHED 并发送相关通知。',
    prerequisites: [
      '批次状态为 COURSE_CONFIRMED 或 ARRANGED，且至少存在一门 CONFIRMED 考试课程。',
      '每门已确认考试课程均已完成考场、座位和至少 1 名监考配置。',
      '发布前再次核对考试时间、考场容量和冲突处理结果。'
    ],
    permissions: [
      '正式发布只允许教务处/TENANT_ALL 执行；学院教务不能越过教务处发布全校考试批次。',
      'ARCHIVED 批次的写操作统一被拒绝，不能通过重新进入页面修改历史考试事实。'
    ],
    steps: [
      '在「考务管理」选择待发布批次，先查看所有 CONFIRMED 考试课程的编排结果。',
      '执行发布前检查。系统逐门确认存在 ACTIVE 考场、已铺座位和至少一名监考。',
      '如存在任何缺项，系统返回“编排不完整”并列出问题；先回排考环节修复，不使用手工说明绕过发布门。',
      '完整性通过后执行正式发布，批次进入 PUBLISHED。',
      '发布成功后系统按真实通知链向考生和监考人员发送考试安排信息；后续考后处理按 FINISHED / ARCHIVED 状态继续。',
      '归档后将批次视为只读历史事实，不再修改考场、座位、监考等正式安排。'
    ],
    warnings: [
      '“排过考场”不等于可以发布：每门已确认课程都必须同时具备考场、座位和监考。',
      '不要在 ARCHIVED 后补改历史考试安排；需要更正时应走产品允许的正式业务路径，而不是直接覆盖归档数据。'
    ],
    successCriteria: [
      '发布前完整性检查无缺项，批次状态成功进入 PUBLISHED。',
      '学生/监考收到的考试安排来自同一批正式发布数据。',
      '后续进入 FINISHED / ARCHIVED 后仍可追溯该批次发布时的正式安排。'
    ],
    troubleshooting: [
      '提示“编排不完整”：按返回课程逐一补考场、座位或监考，再重新执行发布检查。',
      '提示批次状态不允许发布：确认当前确实为 COURSE_CONFIRMED / ARRANGED；PUBLISHED 不重复发布，ARCHIVED 不再写。',
      '通知异常但批次已 PUBLISHED：先核对发布结果和通知任务，不通过重复发布制造第二次正式动作。'
    ]
  }
]
