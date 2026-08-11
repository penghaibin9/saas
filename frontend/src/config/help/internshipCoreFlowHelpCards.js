/**
 * Help Center V3-02 · 岗位实习完整办理链新增节点。
 *
 * 只写已经对照当前 router/service/权限/状态机重新核验的事实：
 * 批次、岗前合规、风险与事故、学生鉴定、实习归档。
 */
export const INTERNSHIP_CORE_FLOW_HELP_CARDS = [
  {
    id: 'in-v3-batch-lifecycle',
    module: '岗位实习中心 · 批次与规则',
    title: '校级管理员如何新建、启用、结束和归档实习批次',
    roles: ['学校管理员', '实习管理员'],
    route: '/admin/internship/batches',
    entry: '岗位实习中心 → 批次与规则 → 实习批次',
    keywords: ['实习批次', 'DRAFT', 'RUNNING', 'CLOSED', 'ARCHIVED', 'VOIDED', 'ADMIN_TENANT', '就绪检查', '强制结束'],
    summary: '批次正式状态机为 DRAFT → RUNNING → CLOSED → ARCHIVED，VOIDED 只允许从草稿到达。批次启用会冻结当前合规规则；结束和归档前会执行真实就绪检查。批次属于全校级写操作，只有后端解析为 ADMIN_TENANT 的校级管理员才能执行。',
    prerequisites: [
      '当前账号必须具备 internship.batch.manage，且后端教师范围解析必须为 ADMIN_TENANT；仅有权限码但仍是 SCOPED 的学院/指导角色不能执行校级批次写操作。',
      '批次编号在当前租户内唯一；开始/结束、报名开始/截止日期不能颠倒，报名截止不能晚于实习结束日期。',
      '需要使用合规模板时，只能绑定当前有效模板；批次启用后合规配置会冻结。'
    ],
    permissions: [
      '批次列表/详情读取使用 internship.batch.view；新建、编辑、启用、结束、归档、作废使用 internship.batch.manage。',
      'service 仍执行 assert_admin_tenant：这是数据范围/作业级二次守卫，不能因为前端路由可见或角色模板含 batch.manage 就认为一定可写。'
    ],
    steps: [
      '新建批次后状态为 DRAFT，配置时间轴、规则、计划人数和当前有效合规模板。草稿阶段可调整规则；启用后规则不能原地追改。',
      '启用时 DRAFT → RUNNING，并把当前合规配置和模板版本冻结到批次事实中。',
      '进行中批次结束前先查看 readiness。系统按 BATCH_CLOSE 规则逐学生重新评估阻断项；有阻断时普通结束会拒绝。',
      '确需强制结束时仍必须是校级管理员，并填写不少于 5 字原因；强制事实和当时合规报告写审计。',
      '批次只有 CLOSED 才能归档。归档前再次检查合规，同时要求学生实习记录已经完成 ARCHIVED；未满足时普通归档拒绝。',
      '草稿批次不再使用时可作废为 VOIDED，原因不少于 5 字且必须携带最新 expectedVersion。'
    ],
    successCriteria: [
      '批次状态只按 DRAFT / RUNNING / CLOSED / ARCHIVED / VOIDED 合法流转，版本号和每次状态变更均有审计。',
      '启用后的合规规则具有冻结版本；结束/归档能追溯当时 readiness/compliance 报告和是否强制。'
    ],
    troubleshooting: [
      '有 internship.batch.manage 仍提示仅校级管理员：检查当前账号数据范围是否仍为 SCOPED；这是后端全校级作业守卫，不是前端按钮故障。',
      '提示批次结束前置检查未通过：打开 readiness/compliance 阻断明细，先处理学生未完成事项，不连续重复点击结束。',
      '提示版本冲突：刷新批次详情，以服务器最新 version/status 重新操作。',
      '多个 RUNNING 批次时不要猜“当前批次”；业务办理应显式选定 batchId。'
    ],
    nextSteps: [
      '批次 RUNNING 后组织学生进入岗位/自主实习申请，并依次完成协议和岗前合规。',
      '批次进入 CLOSED 前应先完成学生考核、成绩发布和学生级归档；所有学生归档后再做批次 ARCHIVED。'
    ],
    contactAdminWhen: [
      '当前账号职责本应是校级管理员但后端仍解析为 SCOPED，需检查角色上下文或数据范围配置。',
      'readiness 报告与具体学生正式状态明显不一致，刷新后仍无法解释阻断项。',
      '批次规则已在 RUNNING 后被错误改写或冻结版本与审计不一致。'
    ]
  },
  {
    id: 'in-v3-onboard-compliance',
    module: '岗位实习中心 · 岗前合规',
    title: '学生什么时候才算真正具备上岗条件',
    roles: ['学生', '实习指导教师', '学院管理员', '学校管理员'],
    route: '/admin/internship/compliance',
    entry: '岗位实习中心 → 就业与归档 → 合规与监管证据',
    keywords: ['岗前合规', 'ONBOARD', 'enterpriseAccess', 'studentConsent', 'guardianConsent', 'safetyEducation', 'agreement', 'insurance', 'specialFiling', 'workRights', 'emergency', '阻断'],
    summary: '“申请通过”或“协议已办”都不等于可以上岗。系统会按当前批次冻结规则对每个实习记录做权威 ONBOARD 合规评估；只有 required 且 applicable 的 BLOCK 项全部 VALID / EXEMPTED / NOT_APPLICABLE，才算没有上岗阻断。',
    prerequisites: [
      '学生已有当前批次下的真实实习主记录和正式去向。',
      '批次已经冻结当前适用的合规规则/模板版本；安全教育使用当前批次全部 ACTIVE 课程的当前版本事实。',
      '查看和办理仍受 internship.compliance.*、保险/安全/知情/备案等具体 permissionCode、数据范围和记录归属共同限制。'
    ],
    permissions: [
      'internship.compliance.view 只代表可查看自己数据范围内的合规结论，不自动获得所有阻断项的修改权。',
      '每类证据使用自己的权限点，例如 insurance.verify、safety.manage、consent.manage、filing.review；豁免申请/审批也有独立权限。'
    ],
    steps: [
      '进入合规工作台选择明确批次，先看“可上岗 / 被阻断”和按 blocker code 的下钻，不凭人工印象判断学生是否准备完成。',
      '逐项处理当前规则实际适用的企业准入、学生知情、监护人确认、安全教育、协议、保险、特殊备案、岗位权益和应急预案等证据。',
      '安全教育不是“上过一次就永久有效”：当前批次要求的全部 ACTIVE 课程必须按当前版本通过并完成承诺。',
      '如学校制度允许豁免，必须走系统真实豁免申请/审批并保留证据；不能在帮助中教用户手工忽略 blocker。',
      '重新执行 ONBOARD 评估；passed=true 且 blockers 为空后，才按当前流程继续上岗。'
    ],
    successCriteria: [
      '合规结论带 ruleVersion/evaluatedAt，可说明学生是按哪一版规则在什么时间得到结论。',
      'required + applicable 的阻断项不存在未处理 BLOCK；已豁免项有正式 EXEMPTED 证据而不是人工备注。'
    ],
    troubleshooting: [
      '协议已 EFFECTIVE 但仍被阻断：不要只看协议，继续检查保险、安全教育、企业准入、知情、备案、岗位权益和应急等当前适用项。',
      '安全教育明明历史通过但仍失败：检查当前批次 ACTIVE 课程版本是否变化、是否漏课或未完成当前版本承诺。',
      '看得到学生但不能修某个 blocker：检查该具体业务权限点和数据范围，compliance.view 本身不是全域写权限。'
    ],
    nextSteps: [
      'ONBOARD 合规通过后进入日常在岗过程：打卡、周报、指导巡访和异常跟进。',
      '实习去向正式变更后应基于新去向重新评估适用的协议、企业准入、保险/备案等合规事实。'
    ],
    contactAdminWhen: [
      '阻断项引用了不存在/跨租户的企业、协议、保险或文件证据。',
      '同一批次同一学生反复评估得到无法解释的不同 ruleVersion，或冻结规则与批次配置不一致。',
      '学校制度确需新增/调整合规规则，而不是某个学生单次操作问题。'
    ]
  },
  {
    id: 'in-v3-risk-incident',
    module: '岗位实习中心 · 风险与事故',
    title: '实习风险和事故如何受理、跟进、升级和关闭',
    roles: ['学生', '实习指导教师', '学院管理员', '学校管理员'],
    route: '/admin/internship/risks',
    entry: '岗位实习中心 → 风险与异常 → 风险学生 / 风险处置；事故和应急在合规工作台办理',
    keywords: ['风险处置', '事故', 'PENDING_HANDLE', 'PROCESSING', 'RESOLVED', 'CLOSED', 'escalate', 'incident', '应急预案'],
    summary: '风险单不是一个颜色标签，而是正式状态链：PENDING_HANDLE → PROCESSING → RESOLVED/CLOSED；升级只提高风险等级，不等于关闭或改变处理状态。事故另有 incident 流程，不能用普通风险关闭代替事故处置。',
    prerequisites: [
      '风险可来自系统预警、打卡异常转风险、指导转风险或人工/学生求助；学生求助会建立真实风险单。',
      '指导教师处理必须命中稳定 advisor_user_id 的本人指导关系；学院/学校角色仍受当前数据范围和具体 permissionCode 约束。',
      '事故上报/处置使用 internship.incident.report / handle；普通风险处置使用 internship.risk.view / handle。'
    ],
    permissions: [
      'INTERN_MENTOR 可在本人指导学生范围处理风险和相关事故；没有稳定指导关系时即使姓名相同也不能获得 owner 权限。',
      '监督只读角色看到风险不等于可以受理、升级或关闭；写动作以具体权限和 owner/scope 为准。'
    ],
    steps: [
      '待处理风险先受理：PENDING_HANDLE → PROCESSING，填写不少于 5 字的受理意见，可指定跟进责任人和截止时间。',
      '处理中持续追加跟进事实。需要提高等级时只能 LOW → MEDIUM → HIGH 单向升级，并填写升级原因；升级不改变 PROCESSING 状态。',
      '风险只有在 PROCESSING / RESOLVED 等允许状态下才能正式关闭，关闭说明不少于 5 字；“老师看过”不等于 CLOSED。',
      '涉及真实事故时使用事故上报和 transition 流程，并按需要维护应急预案；不要只在普通风险备注中记录后就当事故办结。',
      '所有受理、跟进、升级、关闭和事故状态变化保留审计与版本，409 时刷新后再操作。'
    ],
    successCriteria: [
      '风险状态与服务端一致且责任人、最后跟进、风险等级和审计能够串起来；关闭动作有明确结论。',
      '事故记录和应急动作使用独立正式事实，不被普通风险备注替代。'
    ],
    troubleshooting: [
      '指导教师提示只能处置本人学生：检查 advisor_user_id，而不是拿 advisorName 做同名匹配。',
      '风险已经升级但仍显示处理中：这是正常设计，升级改变 level，不负责关闭 status。',
      '提示仅处理中/已化解可关闭：先按当前状态完成受理/跟进，不跳状态。'
    ],
    nextSteps: [
      '风险稳定并正式关闭后继续日常过程管理；如风险源自岗位/单位不适配，转入调岗退岗正式变更。',
      '考核和归档前再次检查是否仍存在开放高风险或开放事故，因为它们可能成为合规/归档阻断。'
    ],
    contactAdminWhen: [
      '学生实际指导教师正确但稳定 advisor_user_id 缺失，导致任何风险 owner 操作都被拒绝。',
      '事故/风险状态和审计轨迹出现不可解释的不一致，按最新 version 重试仍不能恢复。',
      '需要修改学校级风险/事故合规规则，而不是处理单个风险单。'
    ]
  },
  {
    id: 'in-v3-student-evaluation',
    module: '岗位实习中心 · 学生鉴定',
    title: '学生自评、指导教师意见和学校审核如何完成',
    roles: ['学生', '实习指导教师', '学院管理员', '学校管理员'],
    route: '/admin/internship/student-evals',
    entry: '岗位实习中心 → 评价与成绩 → 学生鉴定；学生在本人端提交自评',
    keywords: ['学生鉴定', '自评', 'advisorOpinion', 'SUBMITTED', 'PENDING', 'APPROVED', 'RETURNED', '录审分离'],
    summary: '学生鉴定采用“学生提交 → 指导教师意见 → 学校/学院授权管理员独立审核”。学生正文被退回后修改重交会使旧指导意见失效；指导教师不能既填写意见又代替学校完成终审。',
    prerequisites: [
      '学生账号必须解析到本人有效实习记录；自评总结至少 20 字。',
      '指导教师必须命中本人指导学生的数据范围，填写意见不少于 5 字。',
      '学校审核要求 internship.eval.self.review，同时 service 还校验审核角色必须属于学校/学院授权管理员角色集合。'
    ],
    permissions: [
      '学生只操作本人鉴定；指导教师使用 internship.eval.advisor.manage 对本人指导学生写意见。',
      '“拥有某个 review permissionCode”仍不等于可以学校终审：最终 review() 还执行独立学校审核角色白名单和数据范围校验。'
    ],
    steps: [
      '学生填写自评并提交，submitStatus 进入 SUBMITTED、schoolReviewStatus 为 PENDING；正在审核时不能任意覆盖。',
      '指导教师在本人指导范围填写 advisorOpinion。当前版本、状态和指导关系必须同时满足。',
      '学校/学院授权审核角色核对学生正文和指导教师意见。APPROVE 前必须已经存在指导教师意见；RETURN 必须填写不少于 5 字原因。',
      '被退回后学生在原记录按最新 expectedVersion 修改重交；正文变化会清空旧 advisorOpinion / mentorOpinion，并重新进入 PENDING，因此指导教师必须重新确认新版本。',
      'APPROVED 后学生不能再直接修改；需要纠错必须按正式业务规则处理，不新建第二条绕过版本链。'
    ],
    successCriteria: [
      '学生提交版本、指导教师意见、学校审核人、审核时间和版本链可追溯。',
      '最终 APPROVED 一定建立在当前学生正文版本对应的指导教师意见之上。'
    ],
    troubleshooting: [
      '指导教师有页面权限但学校审核仍 403：这是角色二次守卫；指导教师只能写意见，最终审核由学校/学院授权管理员完成。',
      '退回后发现指导教师意见消失：这是为了防止旧意见代表新正文，学生重交后需要教师重新填写。',
      '提示鉴定已被其他用户修改：刷新详情，以最新 version 继续，不覆盖并发新版本。'
    ],
    nextSteps: [
      '学生鉴定 APPROVED 后，与 APPROVED 企业评价、日常过程数据一起进入实习综合成绩核算。',
      '如果企业评价或其他评分来源仍缺失，先完成对应正式评价，不在成绩页手工补一个“替代分”。'
    ],
    contactAdminWhen: [
      '学生账号无法解析到本人实习记录，导致不能创建/读取本人鉴定。',
      '当前学生实际指导关系正确但教师无法写意见，需检查稳定 advisor_user_id 或权限/范围配置。',
      'APPROVED 后正文与审计中的审核版本不一致。'
    ]
  },
  {
    id: 'in-v3-archive',
    module: '岗位实习中心 · 实习归档',
    title: '实习完成后如何做学生归档、生成归档包并收口批次',
    roles: ['实习指导教师', '学院管理员', '就业教师', '学校管理员'],
    route: '/admin/internship/archive',
    entry: '岗位实习中心 → 就业与归档 → 实习归档 / 材料与证据中心',
    keywords: ['实习归档', 'ARCHIVE', 'archivePassed', '归档快照', '归档包', 'ZIP', 'force', 'internship.archive.force', '证据'],
    summary: '学生归档是否可执行以权威 ARCHIVE 合规评估为准，不以页面七个材料布尔标签作为最终真值。正式归档会冻结材料/合规快照，后续 ZIP 归档包只从该不可变快照生成。强制归档是高危例外，只允许学校管理员且必须有充分原因和依据文件。',
    prerequisites: [
      '归档查看需要 internship.archive.view；真正归档学生需要 internship.archive.execute，并继续受数据范围约束。',
      '普通归档前 ARCHIVE 合规评估必须 passed=true；企业评价、学生鉴定、正式成绩和当前合规规则等以权威评估器返回为准。',
      '强制归档额外需要 internship.archive.force，当前角色必须是 SCHOOL_ADMIN/平台超管，原因至少 10 个汉字并提供依据文件。'
    ],
    permissions: [
      '实习指导教师可以查看本人学生归档状态，但当前权限模板不代表可以执行最终归档。',
      '学院管理员可在本学院范围执行被授予的 archive.execute/package；就业教师以归档查看/打包统计为主；强制归档仅学校管理员。',
      '权限码通过后 service 仍检查记录数据范围、当前状态、版本和强制归档角色证据。'
    ],
    steps: [
      '先在归档台账查看 archivePassed、blockers、ruleVersion 和缺失项；“材料标签 present=true”只用于展示，不替代权威评估。',
      '处理所有 ARCHIVE blockers 后执行普通归档。服务端把 InternshipRecord 推进到 ARCHIVED，并创建/更新正式 InternshipArchive。',
      '归档事务会冻结当时的 material_snapshot、合规规则版本、缺失/豁免和必要数量事实；这份快照成为后续证据包来源。',
      '需要生成归档包时使用 archive.package 权限；ZIP 只从不可变归档快照生成并落文件中心，不重新读取实时业务表拼一个可能漂移的包。',
      '确需强制归档时由学校管理员填写不少于 10 个汉字的原因并提交依据文件；被绕过 blocker、规则版本、批准角色和证据都写入正式记录。',
      '学生级归档全部完成后，再回到批次 readiness，按 RUNNING → CLOSED → ARCHIVED 完成批次级收口。'
    ],
    successCriteria: [
      '学生实习主记录为 ARCHIVED，归档记录、冻结快照、规则版本、操作人和审计能够互相对应。',
      '归档包来自归档快照且可按对象范围下载；强制归档能够明确看到被绕过的 blocker 和依据。'
    ],
    troubleshooting: [
      '页面材料看起来齐全但 archivePassed=false：以权威 ARCHIVE blockers 为准，展开具体 code/reason 排查，不手工改 completeness。',
      '指导教师能看归档却不能点归档：archive.view 与 archive.execute 是不同权限，且 owner/scope 仍要满足。',
      '强制归档提示无权：不能通过学院管理员或普通指导教师代办，只有学校管理员 + archive.force + 原因 + 依据文件才允许。',
      '归档包内容与归档时事实不一致：检查冻结 snapshot/package version；系统不应从已变化的实时表重建旧归档事实。'
    ],
    nextSteps: [
      '确认本批次所有学生均已归档，再查看批次 readiness，处理剩余阻断并结束/归档批次。',
      '需要就业转化/统计时由就业教师或授权角色使用归档/统计结果，不修改已经冻结的实习历史事实。'
    ],
    contactAdminWhen: [
      '权威 ARCHIVE 评估与正式证据明显不一致，或规则版本无法追溯。',
      '归档快照缺失、ZIP 不是从冻结快照生成，或历史归档包与当前版本链不一致。',
      '确需例外强制归档但学校管理员的 archive.force 权限未正确配置。'
    ]
  }
]
