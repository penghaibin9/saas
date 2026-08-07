/**
 * Help Center V3-03 · 毕业设计完整事实链。
 * 只收编当前代码已经证明的正式流程，不用帮助文档补造产品能力。
 */
export const GRADUATION_CORE_FLOW_HELP_CARDS = [
  {
    id: 'gd-v3-batch-setup',
    module: '毕业设计中心 · 批次与规则',
    title: '新一届毕设如何建批次、配置阶段和启用',
    roles: ['毕设管理员', '学校管理员', '学院管理员'],
    route: '/admin/graduation/batches',
    entry: '毕业设计中心 → 毕设批次',
    keywords: ['毕设批次', 'DRAFT', 'RUNNING', 'CLOSED', 'ARCHIVED', 'VOIDED', '阶段时间轴', '查重阈值', '评阅规则', '成绩权重'],
    summary: '毕设批次是整届流程的规则容器，状态为 DRAFT → RUNNING → CLOSED → ARCHIVED，草稿可 VOIDED。启用时会原子初始化当前批次的材料规则和材料目录，后续选题、开题、中期、成果、查重、评阅、答辩和成绩都应绑定真实批次。',
    prerequisites: [
      '批次编号在当前租户内唯一；开始/结束日期和各阶段时间轴必须按时间顺序配置。',
      '成绩权重由指导教师、评阅、答辩三部分组成，总和必须为 100%（允许代码中的 0.5 个百分点浮差）。',
      '查重阈值必须在 0–100 之间；正式使用前应确认选题、开题、中期、成果、查重、评阅、答辩、成绩八阶段口径。'
    ],
    permissions: [
      '页面新建/编辑分别使用 graduationDesign.batch.create / graduationDesign.batch.update，查看使用 graduationDesign.batch.view。',
      '批次记录仍受租户隔离；帮助中的“管理员”不是跳过权限与状态机的凭证。'
    ],
    steps: [
      '新建 DRAFT 批次，填写学年/年级范围、时间、计划人数和阶段时间轴。',
      '配置查重、评阅、答辩和成绩规则；成绩权重不等于 100% 或查重阈值越界时服务端拒绝保存。',
      '确认后启用：只有 DRAFT 可进入 RUNNING；启用事务同时初始化默认材料规则和批次材料目录。',
      '运行中按真实业务推进各阶段；CLOSED / ARCHIVED / VOIDED 批次不能继续按普通编辑入口修改。',
      '仅 RUNNING 可结束为 CLOSED，仅 CLOSED 可归档为 ARCHIVED；VOIDED 只用于草稿作废。'
    ],
    successCriteria: [
      '批次处于预期状态，阶段时间轴和规则可追溯，材料规则/目录已经随启用建立。',
      '后续学生、材料、查重、评阅、答辩和成绩均能明确解析到当前批次，不依赖“默认当前届”的猜测。'
    ],
    troubleshooting: [
      '提示批次编号已存在：换用真实唯一编号，不修改旧批次编号绕过历史事实。',
      '提示阶段顺序错误：检查某阶段开始日期是否早于上一阶段结束日期。',
      '启用/结束/归档失败：先看当前状态；DRAFT、RUNNING、CLOSED 的可执行动作不同。'
    ],
    nextSteps: ['批次 RUNNING 后先确认学生档案与导师关系，再开放选题；不要直接跳到开题或成果。'],
    contactAdminWhen: ['批次已正确配置但前端权限动作与 /graduation/context 返回的 permissionActions 明显不一致。', '批次启用后材料规则或材料目录没有建立，属于基础事实异常，应由管理员排查而不是人工补假状态。']
  },
  {
    id: 'gd-v3-student-mentor',
    module: '毕业设计中心 · 学生与导师',
    title: '学生如何进入毕设、导师关系为什么决定后续数据范围',
    roles: ['毕设管理员', '学院管理员', '专业管理员', '指导老师', '学生'],
    route: '/admin/graduation/mentors',
    entry: '毕业设计中心 → 导师管理与分配；学生台账在「毕设学生」',
    keywords: ['毕设学生', '导师分配', 'mentor_id', 'teacher_no', 'loginName', '数据范围', '学院范围', '专业范围', '同名教师'],
    summary: '权限码只回答能否做动作，毕业设计数据范围还要判断能对哪些学生做。学生本人只认 studentNo/studentId；指导关系优先认 GraduationStudent.mentor_id → GraduationMentor.teacher_no 与当前账号 loginName，姓名只作历史快照，不能作为稳定授权依据。',
    prerequisites: [
      '学生必须存在当前租户的 ACTIVE 毕设学生记录，并绑定正确批次。',
      '学院/专业管理员必须在登录上下文中带有 collegeId(s) / majorId(s)；缺失时系统不猜范围，默认看不到学生。',
      '指导教师应先建立真实导师台账和稳定 mentor_id 关系；重名或改名不应改变授权结果。'
    ],
    permissions: [
      '导师管理/分配页面使用 graduationDesign.mentor.manage，学生台账使用对应 student view/manage 权限。',
      '完整访问范围由 graduation_scope_service 再裁决：全校角色、学院/专业 claim、本人导师关系、评阅关系、答辩席位和学生本人关系各自独立。'
    ],
    steps: [
      '管理员把本届学生纳入真实毕设批次，核对资格、学院/专业和 ACTIVE 状态。',
      '建立导师台账并按服务端允许范围完成学生—导师分配，形成稳定 mentor_id。',
      '指导教师登录后，系统优先通过导师台账 teacher_no 与当前 loginName 判断本人学生，不以 advisor_name 同名匹配扩大权限。',
      '学院/专业管理员通过 token 中 collegeId(s)/majorId(s) 收敛数据；没有范围 claim 时先修配置并重新登录。',
      '学生本人只按 studentNo/studentId 访问本人毕设档案，不能按姓名反查。'
    ],
    successCriteria: ['每名学生的批次、组织归属和导师 ID 可稳定追溯；同名教师不会互相看到对方学生。', '页面列表、统计、导出和单条操作使用同一 scope/owner 口径。'],
    troubleshooting: ['指导老师姓名正确但看不到学生：优先检查 mentor_id、导师 teacher_no 与登录 loginName，不要改成按姓名放行。', '学院/专业管理员进入后列表为空：检查 /graduation/context 的 scopeConfigured 与 collegeId/majorId claim。', '学生本人找不到毕设档案：检查 studentNo/studentId 与当前 ACTIVE 毕设学生记录的绑定。'],
    nextSteps: ['学生和导师关系稳定后，进入选题轮次；选题正式确定后再下达任务书。'],
    contactAdminWhen: ['历史学生只有导师姓名、没有稳定 mentor_id，导致正常教师被 fail-closed。', '组织 claim 配置正确且重新登录后，服务端仍把本学院/本专业学生判为越权。']
  },
  {
    id: 'gd-v3-taskbook',
    module: '毕业设计中心 · 任务书',
    title: '任务书如何下达、学生确认，变更后为什么要重新确认',
    roles: ['指导老师', '学生', '学院管理员'],
    route: '/admin/graduation/process',
    entry: '毕业设计中心 → 过程指导（任务书/指导记录/中期检查）',
    keywords: ['任务书', 'PENDING_CONFIRM', 'CONFIRMED', 'CHANGE_PENDING', '学生确认', '代确认', '历史版本'],
    summary: '任务书正式链是导师下达 → 学生确认 → 如有变更则形成新版本并重新确认。一名学生只有一条当前任务书；变更保留旧内容快照并增加版本号，不能直接覆盖已确认任务书。',
    prerequisites: ['学生已经分配导师且在当前操作者的数据范围内。', '首次下达前不存在另一条当前任务书；已有任务书需要走变更。', '管理员代学生确认属于受控例外，必须通过 taskbook policy 且填写不少于 5 字原因。'],
    permissions: ['任务书更新使用 graduationDesign.taskbook.update，导出使用 graduationDesign.taskbook.export。', '单个学生操作还必须通过 assert_student_access；指导教师必须具有该生稳定导师关系。'],
    steps: ['指导教师下达任务目标、内容、进度安排和成果要求，生成 v1，状态 PENDING_CONFIRM。', '学生本人确认后进入 CONFIRMED；如果学生阶段是 TASKBOOK_CONFIRM，则推进到 GUIDING。', '已 CONFIRMED 的任务书需要调整时填写不少于 5 字变更原因；旧版本写入 history，版本号 +1，状态变为 CHANGE_PENDING。', '学生对变更版本重新确认，不能让旧确认继续代表新内容。', '非学生代确认必须走授权策略并单独写“管理员代确认任务书”审计。'],
    successCriteria: ['当前任务书是 CONFIRMED，版本、确认时间和历史快照可追溯。', '任何变更都不会静默继承旧确认。'],
    troubleshooting: ['提示已有任务书：不要重复下达，使用变更。', '学生确认后仍不能进入指导：检查学生阶段是否为 TASKBOOK_CONFIRM，以及事务是否成功提交。', '指导教师看不到任务书：检查本人导师稳定关系与 student scope，而不是只看 advisor_name。'],
    nextSteps: ['任务书确认后进入开题/指导过程；当前学生提交开题报告还会再次校验存在 CONFIRMED 任务书。'],
    contactAdminWhen: ['任务书内容与版本历史不一致，或学生确认哈希/签署记录缺失影响最终归档。', '正常本人导师关系已确认但任务书仍被业务关系守卫拒绝。']
  },
  {
    id: 'gd-v3-guidance-midterm',
    module: '毕业设计中心 · 指导与中期',
    title: '日常指导和中期检查怎么形成整改闭环',
    roles: ['指导老师', '学生', '学院管理员'],
    route: '/admin/graduation/process',
    entry: '毕业设计中心 → 过程指导（任务书/指导记录/中期检查）',
    keywords: ['指导记录', '指导计划', '中期检查', 'PENDING', 'CHECKED_PASS', 'RECTIFYING', 'RECTIFY_SUBMITTED', 'RECTIFIED_PASS', 'CHECKED_FAIL'],
    summary: '中期检查不是简单“通过/不通过”。正式状态包含待检查、通过、限期整改、整改待复核、整改通过和不通过；整改可以反复退回再改。读取中期详情不会偷偷建记录，首次真实检查才创建事实。',
    prerequisites: ['中期检查只允许学生处于 MIDTERM / FINAL_CHECK 相关阶段。', '过程指导、计划和中期数据必须在当前批次和操作者学生范围内。', '需要整改时学生必须提交非空整改说明，复核只处理 RECTIFY_SUBMITTED。'],
    permissions: ['中期检查动作对应 graduationDesign.midterm.review，指导计划/记录使用 graduationDesign.guidance.*。', '有 permissionCode 仍必须通过 assert_student_access；导师/学院等角色各按真实业务关系和组织 scope 办理。'],
    steps: ['导师持续记录指导和指导计划；计划签到后保留留痕，已签到计划不能再取消。', '中期检查选择 PASS / RECTIFY / FAIL：PASS 进入 CHECKED_PASS；RECTIFY 进入 RECTIFYING；FAIL 进入 CHECKED_FAIL 并将学生风险提升为 HIGH。', '限期整改学生提交说明后进入 RECTIFY_SUBMITTED。', '教师复核：PASS → RECTIFIED_PASS；FAIL 在这里表示退回再整改，回到 RECTIFYING 并累计整改次数。', '通过中期后，学生从 MIDTERM 推进到 FINAL_CHECK，为成果提交建立前置事实。'],
    successCriteria: ['中期结论和整改每次流转都有状态与审计，不通过不会被伪装成已完成。', '通过/整改通过的学生才具备后续成果提交前置。'],
    troubleshooting: ['打开中期详情却列表没有记录：未开始时返回虚拟 PENDING 是正常行为，GET 不应产生写库记录。', '提示当前阶段不可检查：先核对学生 stage，不通过前端强行创建。', '已签到指导计划无法取消：这是留痕保护，不能删掉已发生事实。'],
    nextSteps: ['中期 CHECKED_PASS / RECTIFIED_PASS 后进入成果初稿与定稿提交。'],
    contactAdminWhen: ['中期状态已通过但学生阶段没有推进到 FINAL_CHECK。', '批次选择正确但指导/中期列表与单条详情使用了不同数据范围。']
  },
  {
    id: 'gd-v3-final-submission',
    module: '毕业设计中心 · 成果定稿',
    title: '成果初稿、定稿如何提交和审核，为什么定稿还要查重',
    roles: ['学生', '指导老师', '学院管理员'],
    route: '/admin/graduation/finals',
    entry: '毕业设计中心 → 成果提交；材料版本可在「毕设材料中心」查看',
    keywords: ['成果', '初稿', '定稿', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', '材料版本', '查重'],
    summary: '成果分初稿和定稿。学生必须先通过中期，初稿通过后才能提交定稿；每次提交绑定真实文件和材料版本。定稿审核通过前还会校验当前定稿查重已完成且未超标，或超标复查已经通过。',
    prerequisites: ['学生 stage 必须处于 FINAL_CHECK / DEFENSE，且选题有效、资格不是 UNQUALIFIED。', '中期必须为 CHECKED_PASS / RECTIFIED_PASS。', '成果提交必须绑定一个可用于业务的真实主文档文件；已有 PENDING_REVIEW 成果时不能重复提交。'],
    permissions: ['学生只能提交本人材料；成果查看/审核使用 graduationDesign.final.view / graduationDesign.final.review 等对应权限。', '审核还必须通过学生数据范围与权威材料版本 expectedVersion + fileVersionId 冲突保护。'],
    steps: ['学生先提交初稿；系统生成该类型版本并进入 PENDING_REVIEW。', '初稿审核通过后才允许提交定稿；定稿不能绕过初稿 APPROVED 前置。', '定稿提交后先完成查重；查重未 DONE 时不能 APPROVE 定稿。', '查重超阈值且复查没有 APPROVED 时，定稿审核不能直接通过。', '审核动作同时落业务记录和权威材料版本，旧文件版本继续保留。'],
    successCriteria: ['存在 APPROVED 的正式定稿，并且对应文件版本、审核人、审核时间和查重事实可追溯。', '后续评阅任务只绑定这份权威 APPROVED 定稿。'],
    troubleshooting: ['提示中期未通过：先回中期整改链处理。', '提示请先提交初稿并审核通过：不能直接上传定稿绕过。', '定稿审核提示查重未完成/超标：进入查重台账处理，不在成果页人工改状态。'],
    nextSteps: ['定稿文件进入查重；查重满足规则后，分配独立评阅任务，再进入答辩。'],
    contactAdminWhen: ['成果业务记录与材料中心 current file version 不一致。', '查重已完成且复查条件满足，但定稿审核仍读取旧查重记录。']
  },
  {
    id: 'gd-v3-plagiarism',
    module: '毕业设计中心 · 查重',
    title: '查重如何发起、回填结果，超标后怎样申请复查',
    roles: ['学院管理员', '查重管理员', '学生'],
    route: '/admin/graduation/plagiarism-ledger',
    entry: '毕业设计中心 → 查重台账',
    keywords: ['查重', 'CHECKING', 'DONE', 'FAILED', 'overThreshold', '复查', 'PENDING', 'APPROVED', 'REJECTED'],
    summary: '查重任务状态为 CHECKING / DONE / FAILED。发起任务必须绑定真实成果附件；同一成果有进行中任务时复用而不是重复创建。只有 DONE 且超阈值的记录才能申请一次正式复查，复查批准会创建新的 CHECKING 任务而不是修改原结果。',
    prerequisites: ['先有需要检测的 GraduationFinal，并且成果带有可检测附件。', '重复率必须在 0–100；报告地址只允许 HTTPS 或平台内部 /api/v1/ 地址。', '复查理由不少于 5 字；同一原查重记录不能重复生成复查任务。'],
    permissions: ['发起、回填、复查审核分别对应 graduationDesign.plagiarism.start / result / disputeReview；查看使用 graduationDesign.plagiarism.view。', '所有动作还会按目标学生调用 assert_student_access，不能靠查重权限跨越本人/学院/导师等数据范围。'],
    steps: ['对指定成果发起查重，进入 CHECKING；若已有该成果进行中的任务则直接返回现有任务。', '授权人员回填真实重复率和可访问报告地址，状态变 DONE，并计算 overThreshold。', '只有 DONE + overThreshold 才能申请复查，复查状态进入 PENDING。', '复查审核 APPROVE 时创建新的 CHECKING 记录并通过 recheck_of_id 关联原记录；REJECT 时保留原结果和理由。', '新复查结果仍超标时，应针对新记录继续按允许业务处理，不覆盖原检测事实。'],
    successCriteria: ['原查重、复查申请、新复查任务和最终结果形成不可覆盖的链。', '定稿审核读取真实最新规则条件，不通过手工修改 overThreshold 绕过。'],
    troubleshooting: ['提示已有进行中查重：等待/处理现有 CHECKING，不重复发起。', '复查按钮不可用：核对原记录是否 DONE 且 overThreshold=true。', '复查已处理：不能对同一原记录重复生成任务；按新查重记录继续。'],
    nextSteps: ['满足定稿审核条件并形成 APPROVED 定稿后，分配独立评阅任务。'],
    contactAdminWhen: ['查重结果已 DONE 但成果定稿仍读不到对应 gd_final_id。', '复查批准后没有生成 recheck_of_id 关联的新任务或通知事实不一致。']
  },
  {
    id: 'gd-v3-review',
    module: '毕业设计中心 · 成果评阅',
    title: '成果评阅如何分配，为什么指导教师不能评自己的学生',
    roles: ['学院管理员', '评阅教师'],
    route: '/admin/graduation/review-tasks',
    entry: '毕业设计中心 → 评阅任务',
    keywords: ['评阅', 'ASSIGNED', 'REVIEWING', 'COMPLETED', 'RETURNED', 'reviewer_mentor_id', '双盲', 'SoD', '回避'],
    summary: '评阅是独立职责，不等于指导教师意见。分配评阅时必须选择已绑定导师台账的稳定评阅人，并禁止与该生指导教师发生 SoD 冲突；评阅任务只绑定 APPROVED 正式定稿，提交时普通评阅教师只认 reviewer_mentor_id。',
    prerequisites: ['必须先有 final_type=定稿 且 status=APPROVED 的权威成果。', '评阅人必须来自真实导师台账并有稳定 reviewer_mentor_id。', '评阅人不得是该生指导教师；默认批次规则是 DOUBLE_BLIND、至少 2 名评阅人，但以当前批次规则为准。'],
    permissions: ['任务分配使用 graduationDesign.review.assign，提交 graduationDesign.review.submit，退回 graduationDesign.review.return，查看 graduationDesign.review.view。', 'GD_REVIEWER 的学生访问关系只认 GraduationReview.reviewer_mentor_id；姓名仅是快照，历史缺稳定 ID 时 fail-closed。'],
    steps: ['管理员在通过的正式定稿上分配评阅人；系统校验导师回避冲突。', '任务状态从 ASSIGNED / REVIEWING 进入评阅办理；同一评阅人同一权威定稿的活动任务不会重复创建。', '评阅教师提交分数和意见时，系统把当前登录导师 ID 与 reviewer_mentor_id 比对；不匹配即拒绝。', '提交成功进入 COMPLETED；需要退回时保留正式退回状态和原因，不直接改成另一位教师的完成记录。', '成绩核算只读取权威定稿对应的 COMPLETED 评阅结果。'],
    successCriteria: ['所有评阅任务都绑定明确 reviewer_mentor_id 和权威定稿，指导教师回避规则成立。', '成绩来源能反查到真实 COMPLETED 评阅任务。'],
    troubleshooting: ['评阅教师看到学生但提交 403：检查 reviewer_mentor_id 是否就是本人导师台账 ID。', '提示评阅人与导师冲突：必须换评阅人，不能靠管理员身份把同一教师当独立评阅。', '历史评阅只有 reviewer_name 没有稳定 ID：需要治理数据，不能恢复姓名授权。'],
    nextSteps: ['完成批次要求的评阅后进入答辩安排/评分；答辩席位同样使用稳定身份。'],
    contactAdminWhen: ['任务分配正确但 reviewer_mentor_id 与当前账号导师身份解析持续不一致。', '正式定稿已经更新，但评阅任务仍绑定旧定稿版本，需要先查权威来源。']
  },
  {
    id: 'gd-v3-archive',
    module: '毕业设计中心 · 归档',
    title: '毕业设计如何生成清单、提交、备案，备案后为什么不能再改',
    roles: ['学院管理员', '毕设管理员', '学校管理员'],
    route: '/admin/graduation/risk-archive',
    entry: '毕业设计中心 → 问题预警/毕设归档/毕设统计；真实文件版本在「毕设材料中心」',
    keywords: ['毕设归档', 'NOT_GENERATED', 'PENDING_SUBMIT', 'SUBMITTED', 'FILED', 'REJECTED', 'Manifest', 'SHA-256', '归档快照', '解档'],
    summary: '学生归档状态为 NOT_GENERATED → PENDING_SUBMIT → SUBMITTED → FILED，SUBMITTED 可被 REJECTED 后补交。默认必备事实包括已确认任务书、已通过开题/中期/定稿、完成评阅、确认答辩评分和已发布成绩；正式备案还冻结真实文件 SHA-256、任务书正文/学生确认哈希和 manifestHash。',
    prerequisites: ['提交归档前必备项齐全且没有 OPEN / PROCESSING 风险。', '正式定稿必须有可核验文件证据；任务书必须有学生本人确认哈希。', '批次可以通过 rules_config.archive.requiredItems 收敛必备项，但只能从代码允许的正式清单中配置。'],
    permissions: ['归档备案/Manifest 使用 graduationDesign.archive.file，导出任务使用 graduationDesign.archive.export；查看仍受学生数据范围。', '批量归档采用先预览后执行的签名 previewToken；执行时会锁定并重算快照，操作者、scope 或数据发生变化就 409。'],
    steps: ['生成归档清单，系统重新检查任务书、开题、中期、定稿、评阅、答辩评分和成绩等真实状态。', '只有 PENDING_SUBMIT、必备项无缺失且没有开放风险时才能提交为 SUBMITTED。', '备案时再次重算完整性，生成/校验真实 Manifest，写 archiveBatchNo、manifestHash，并把学生 stage 推进到 ARCHIVED。', '材料中心冻结 Manifest 时纳入任务书快照哈希、学生确认哈希、开题/定稿 FileObject.sha256 等真实证据。', 'FILED/ARCHIVED 后 ORM 终态守卫禁止再修改任务书、开题、中期、指导、成果、查重、评阅、答辩评分、成绩、申诉等归档证据。当前产品没有“绕过守卫修改”的合法路径。'],
    successCriteria: ['归档记录为 FILED，学生 stage=ARCHIVED，Manifest/文件哈希/版本和归档批次号可追溯。', '归档后证据保持不可变，后续 ZIP/XLSX 导出来自已冻结事实并通过受控下载票据。'],
    troubleshooting: ['提交提示缺材料：按 missingItems 回到对应业务节点补齐，不手工改归档状态。', '提示仍有未关闭风险：先完成风险闭环。', '批量执行提示预览过期/数据变化：重新预览获取新 previewToken，不复用旧快照。', '备案后发现事实错误：当前必须先建设并执行正式解档审批流程，不能直接改 ORM 证据。'],
    nextSteps: ['备案后进入归档导出/审计；毕设归档完成并不等于教务毕业资格自动通过，毕业资格由教务综合规则独立裁决。'],
    contactAdminWhen: ['完整性检查与材料中心真实版本明显不一致，或 FILED 记录缺 manifestHash / 文件 SHA-256。', '确需更正已备案事实时，需要产品级“解档审批”能力；当前不能让普通管理员直接改数据。']
  }
]
