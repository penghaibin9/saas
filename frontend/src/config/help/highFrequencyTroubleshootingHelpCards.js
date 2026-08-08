/**
 * Help Center V3-05 · 高频故障库（首批）。
 *
 * 只解释仓库当前已经存在的统一错误契约、状态机保护、Excel 预校验和敏感数据边界；
 * 不把“可能原因”写成绕过后端校验的操作建议。
 */
import { HELP_AUTHORIZATION_PRINCIPLE } from './helpRoleGuidance.js'

const COMMON_ROLES = ['学生', '任课教师', '辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员']

export const HIGH_FREQUENCY_TROUBLESHOOTING_HELP_CARDS = [
  {
    id: 'tr-v3-permission-scope-403',
    module: '高频故障库 · 权限与数据范围',
    title: '出现 403、按钮灰色或看不到数据时怎么判断是权限还是数据范围',
    roles: COMMON_ROLES,
    entry: '帮助中心 → 我遇到问题；保留当前页面、业务对象和 traceId 后按本卡排查',
    keywords: ['403', '权限', '按钮灰色', '看不到', 'NO_PERMISSION', 'NO_DATA_SCOPE', '403001', '403002', '数据范围'],
    summary: '统一响应把 NO_PERMISSION 映射为 403001，把 NO_DATA_SCOPE 映射为 403002。能进入页面不代表能处理任意记录：真正授权仍由 permissionCode、数据范围、业务关系/记录归属和当前状态共同裁决。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['先记录错误 bizCode、message 和 traceId；不要只凭前端按钮是否显示判断权限。', '确认当前登录角色、学校、学院/班级/本人关系和目标记录是否正确。'],
    permissions: ['NO_PERMISSION 表示动作权限/角色边界不满足；NO_DATA_SCOPE 表示目标数据不在当前用户允许范围。', '学校管理员等高权限角色仍不能绕过状态机、稳定 owner/assignee 或本人关系。'],
    steps: ['先看响应 bizCode：NO_PERMISSION 与 NO_DATA_SCOPE 分开处理。', 'NO_PERMISSION：核对当前角色是否有该动作的 permissionCode，以及业务节点是否允许该角色办理。', 'NO_DATA_SCOPE：核对学院、班级、授课、导师、辅导员、学生本人等稳定关系，不通过改前端筛选扩大范围。', '刷新服务器最新详情和 allowedActions；若服务端不返回动作，前端不应自行补按钮。'],
    successCriteria: ['刷新后只展示当前用户真实可见数据和服务器允许动作。', '权限修复后仍保持跨学院、跨班级、跨本人关系 fail-closed。'],
    troubleshooting: ['只有页面权限但写操作 403：继续检查端点动作权限、数据范围和当前节点。', '同名教师/学生不能作为稳定授权依据，应核对 teacher_key、studentId、mentorId、advisor_user_id 等正式关系。'],
    nextSteps: ['权限或范围恢复后重新加载详情，再执行一次目标动作，不连续重复点击旧页面。'],
    contactAdminWhen: ['确认 permissionCode、数据范围、稳定业务关系和当前状态都正确，刷新后仍持续返回同一 403。', '发现跨学院/跨班级/跨本人关系数据反而可见，应立即按越权缺陷处理。']
  },
  {
    id: 'tr-v3-version-conflict-409',
    module: '高频故障库 · 并发与版本',
    title: '提示 409、版本冲突或“请刷新”时不要重复提交',
    roles: COMMON_ROLES,
    entry: '发生提交、审批、发布、退回等写操作冲突时，先保留错误提示并刷新服务器真值',
    keywords: ['409', '版本冲突', 'APPROVAL_VERSION_CONFLICT', 'DATA_CONFLICT', 'IDEMPOTENCY_CONFLICT', '409001', 'expectedVersion', '请刷新'],
    summary: '统一响应把 DATA_CONFLICT、APPROVAL_VERSION_CONFLICT、IDEMPOTENCY_CONFLICT 映射为 409001。多数正式写操作使用 expectedVersion/幂等保护，别人先处理后，旧页面不能继续覆盖新事实。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认不是网络超时后反复点击造成重复请求；保留 traceId。', '知道当前记录的最新状态、version/expectedVersion 和最近一次处理结果。'],
    permissions: ['409 通常不是“给更大权限”就能解决；它表示当前事实已经变化或请求与服务器状态冲突。'],
    steps: ['停止重复提交，重新打开或刷新当前记录。', '读取服务器返回的最新状态、version 和 allowedActions。', '若别人已处理，按新状态继续下一步；若仍需本人处理，使用刷新后的版本重新提交一次。', '幂等冲突时先确认第一次请求是否已经成功形成事实，不能为了“看起来没反应”重复制造第二笔业务。'],
    successCriteria: ['最终只形成一次正式业务结果，不出现旧页面覆盖新状态或重复审批/重复发放。'],
    troubleshooting: ['刷新后按钮消失通常表示状态已推进，不要强行恢复旧动作。', '持续 409 时核对是否有后台任务、另一审批人或移动端已经先处理。'],
    nextSteps: ['以刷新后的服务器状态继续业务链，而不是回到旧页面重放请求。'],
    contactAdminWhen: ['刷新后 version 未变化、状态也未变化，但同一合法动作稳定返回 409。', '发现同一幂等请求产生两笔正式事实。']
  },
  {
    id: 'tr-v3-assignee-not-configured',
    module: '高频故障库 · 审批受理人',
    title: '提示 ASSIGNEE_NOT_CONFIGURED：先修责任关系，不要绕过审批流',
    roles: ['辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员'],
    entry: '提交或推进审批时出现“未配置受理人/ASSIGNEE_NOT_CONFIGURED”',
    keywords: ['ASSIGNEE_NOT_CONFIGURED', '未配置受理人', '受理人', 'assignee', 'WorkflowTask', '待办'],
    summary: 'ASSIGNEE_NOT_CONFIGURED 在统一响应中属于可修复业务配置错误。正式审批节点必须能解析到具体 assignee；不能通过改状态、临时放宽权限或跳过 WorkflowTask 来“先办完再说”。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认目标学生/业务对象的班级、学院、教师/导师/辅导员责任关系已经建立。', '确认当前流程确实已经到需要该受理人的审批节点。'],
    permissions: ['责任关系解决“谁应该收到任务”，permissionCode 和数据范围继续决定“这个人是否有权办理”。两者缺一不可。'],
    steps: ['根据错误发生的节点确认需要哪类受理人：辅导员、学院、教务/学工处或其他稳定 owner。', '到组织岗位/业务责任配置中修复对应关系，不直接修改业务记录状态。', '重新加载业务详情，确认产生具体 WorkflowTask/UnifiedTodo 和 assignee。', '由真实受理人处理后再继续下一节点。'],
    successCriteria: ['当前节点存在唯一可解释的具体受理人，待办与业务状态一致。', '没有通过默认管理员、姓名匹配或前端 fallback 绕过正式责任关系。'],
    troubleshooting: ['组织有老师但仍未配置：检查是否缺少班级辅导员、学院负责人、导师/任课教师等业务关系。', '待办存在但受理人不对：先修稳定关系并对账，不把旧错误待办继续流转。'],
    nextSteps: ['责任关系修复后重新进入原业务，不新建重复申请来规避旧流程。'],
    contactAdminWhen: ['责任关系已正确、刷新后仍无法生成具体 assignee。', '同一节点出现多个相互冲突的在途待办或指派到无关人员。']
  },
  {
    id: 'tr-v3-returned-cannot-continue',
    module: '高频故障库 · 退回与驳回',
    title: '被退回后不能继续：先确认 RETURNED，不要把 REJECTED 当可修改',
    roles: COMMON_ROLES,
    entry: '业务被退回/驳回后，重新进入详情确认服务器当前状态和 allowedActions',
    keywords: ['退回', 'RETURNED', 'REJECTED', 'RESUBMIT', 'EDIT_RETURNED', '重新提交', '驳回'],
    summary: 'RETURN/RETURNED 通常表示退回修改后可按状态机继续，REJECT/REJECTED 通常表示本次流程终止。不同业务的可修改字段和重新提交动作由服务端状态机决定，前端不能统一伪造“重新提交”。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['先看服务端当前状态，不只看通知文案。', '阅读退回/驳回原因并确认是否需要补材料、改字段或重新发起新业务。'],
    permissions: ['能查看退回原因不等于拥有编辑/重提权限；仍受本人关系、数据范围和 allowedActions 约束。'],
    steps: ['状态是 RETURNED：查看允许动作，例如 EDIT_RETURNED / RESUBMIT 或该模块定义的等价动作。', '按退回原因修改允许字段、材料或事实，不覆盖历史审批意见。', '刷新版本后再重新提交，让流程生成新的在途节点。', '状态是 REJECTED：不要寻找隐藏重提按钮；按该模块规则决定重新发起还是结束。'],
    successCriteria: ['退回修改保留原审批轨迹并产生新的后续节点；驳回不会被前端伪装成可继续的退回。'],
    troubleshooting: ['RETURNED 但没有任何允许动作：检查当前角色/本人关系和服务端 allowedActions。', 'REJECTED 仍出现“继续审批/重新提交”：属于状态机展示缺陷，应停止操作。'],
    nextSteps: ['重新提交成功后回到新的审批链；必要时通知下一受理人，不删除旧历史。'],
    contactAdminWhen: ['服务端明确 RETURNED 且责任/权限正确，但刷新后仍无任何合法修改或重提入口。', '发现 REJECTED 可以直接改回在途状态而没有正式新流程。']
  },
  {
    id: 'tr-v3-publish-blocked',
    module: '高频故障库 · 发布门',
    title: '为什么发布被阻断：发布不是保存，先补齐正式前置事实',
    roles: ['任课教师', '辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员'],
    entry: '成绩、选课、考务、毕设、实习等页面执行“发布/确认正式”动作时',
    keywords: ['发布', '发布被阻断', '发布失败', '前置校验', '正式发布', '状态机', '快照', 'READY'],
    summary: '正式发布动作会把草稿/在途数据推进为可被其他模块消费的正式事实，因此服务端会重验前置状态、名单/来源快照、完整性、冲突、材料和当前版本。不能靠前端把按钮点亮绕过发布门。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认当前记录已经到允许发布的状态，而不是草稿、审核中、退回或归档终态。', '确认前置数据、人员名单、必填材料、审核结论和服务端要求的快照已经形成。'],
    permissions: ['有发布 permissionCode 只解决“谁可尝试发布”；发布门仍会校验业务完整性、数据范围和当前状态。'],
    steps: ['读取服务端明确提示，定位缺的是状态、前置事实、冲突、材料还是版本。', '回到对应前置业务修复，不直接编辑最终发布结果。', '重新执行预校验/审核/确认，让服务端生成新的可发布真值。', '刷新后只在 allowedActions 明确包含发布动作时再次提交。'],
    successCriteria: ['发布成功后其他模块只消费服务器正式事实，并保留发布版本/快照/审计。'],
    troubleshooting: ['按钮有权限但发布失败：优先检查前置事实，不先加管理员权限。', '发布后又修改来源数据：按模块正式变更/撤回/重新发布机制处理，不能静默覆盖。'],
    nextSteps: ['发布成功后核对下游名单、成绩、排考、归档等消费结果是否与本次正式版本一致。'],
    contactAdminWhen: ['所有前置校验均已通过、状态和版本正确，服务端仍稳定阻断且不给可解释业务提示。', '发现未经过发布门的数据已经被下游当正式事实消费。']
  },
  {
    id: 'tr-v3-import-error-rows',
    module: '高频故障库 · Excel 导入',
    title: 'Excel 导入失败：先预校验并下载错误行，不要反复整表导入',
    roles: ['辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员'],
    entry: '支持批量导入的页面 → 下载 Excel 模板 → 上传 → 预校验 → 错误行 → 确认导入',
    keywords: ['导入', '导入失败', '错误行', 'Excel', 'xlsx', '预校验', 'invalidRows', 'previewToken', '失败数据未导入'],
    summary: '公共 Excel 导入组件采用“模板 → 上传 → 预校验 → 错误行 → 确认导入”合同。invalidRows > 0 时前端禁止确认；确认阶段携带 previewToken，失败数据不应被伪装成成功。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['使用当前页面下载的最新 .xlsx 模板，不自行改表头/必填列含义。', '保留预校验返回的 rows、errors、invalidRows 和 previewToken。'],
    permissions: ['导入能力仍受模块写权限和数据范围约束；模板能下载不代表可以向任意学院/班级写数据。'],
    steps: ['先上传文件执行预校验，不直接写正式库。', '查看无效行数量和每行错误原因；有错误行时下载错误行 Excel。', '只修正错误行对应的格式、必填、引用关系或业务冲突，然后重新上传预校验。', 'invalidRows=0 后再确认导入；确认时使用本次预校验返回的 previewToken。', '导入完成后查看成功条数和通用导入记录/审计，不把失败行当成功。'],
    successCriteria: ['只有通过预校验的数据进入正式库；失败行可定位、可修正、可重新导入，并有导入审计。'],
    troubleshooting: ['“确认导入”按钮灰色：先看 invalidRows 是否大于 0。', '模板字段看似正确仍失败：重新下载当前模板，避免使用历史模板。', '预校验后数据已变化导致确认失败：重新预校验生成新的 previewToken。'],
    nextSteps: ['导入后抽查关键记录，并在导入台账核对本次成功/失败数量。'],
    contactAdminWhen: ['错误行下载失败或 errors 与页面错误数量不一致。', 'invalidRows=0 且 previewToken 有效，但确认导入仍稳定失败或出现部分成功无回执。']
  },
  {
    id: 'tr-v3-todo-still-pending',
    module: '高频故障库 · 待办一致性',
    title: '业务已经处理成功但待办还在：先对账业务状态、WorkflowTask 和 UnifiedTodo',
    roles: ['任课教师', '辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员'],
    entry: '教师/管理端待办中心或业务详情：处理完成后仍看到旧待办时',
    keywords: ['待办', '处理后待办还在', 'UnifiedTodo', 'WorkflowTask', 'PENDING', 'DONE', 'assignee', '刷新'],
    summary: '正式审批通常同时维护业务状态、WorkflowTask 和 UnifiedTodo。页面缓存或刷新时机会造成短暂显示差异，但服务端三者长期不一致不能靠“手工隐藏待办”解决。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认刚才写操作已经返回成功，而不是超时/409/403。', '记录业务对象 id、当前状态、待办标题和 traceId。'],
    permissions: ['只对账本人有权查看的业务和待办；不要为了清待办扩大数据范围或把任务转给无业务关系人员。'],
    steps: ['刷新业务详情，确认服务器业务状态是否已经推进。', '刷新待办列表，确认 WorkflowTask/UnifiedTodo 是否仍为 PENDING。', '若业务仍旧状态，按原业务错误处理；不要先删待办。', '若业务已成功推进但待办长期仍 PENDING，应按一致性缺陷修复任务状态/重建投影，并保留审计。'],
    successCriteria: ['业务状态、当前 WorkflowTask 和 UnifiedTodo 对同一节点给出一致结论；完成任务不再作为在途待办展示。'],
    troubleshooting: ['刚处理完立即仍显示：先刷新一次，排除前端缓存。', '同一业务出现多个 PENDING 待办：检查是否重复提交、错误重试或受理人变更后旧任务未关闭。'],
    nextSteps: ['待办对账一致后继续下一业务节点；不要创建重复申请来“顶掉”旧待办。'],
    contactAdminWhen: ['业务已进入下一状态或终态，但 WorkflowTask/UnifiedTodo 仍长期 PENDING。', '同一节点出现多个有效受理人任务且无法由业务规则解释。']
  },
  {
    id: 'tr-v3-sensitive-data-denied',
    module: '高频故障库 · 敏感数据',
    title: '敏感字段看不到或只显示脱敏值：先确认这是安全边界，不要要求前端直接展示明文',
    roles: ['辅导员', '学院管理员', '学工处管理员', '学校管理员'],
    entry: '家庭经济、心理、证件、联系方式等敏感数据详情或 reveal 操作',
    keywords: ['敏感数据', '脱敏', 'SENSITIVE_VIEW', '心理', '家庭经济', '明文', '审计', '503', 'fail-closed', 'traceId'],
    summary: '敏感字段默认最小暴露。即使有页面查看权限，明文 reveal 仍可能要求专门敏感权限、真实数据范围、业务关系、查看原因和安全审计；审计/安全依赖失败时应 fail-closed，而不是返回明文。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认当前确有业务必要查看敏感原文，并准备填写真实查看原因。', '确认目标学生在本人合法数据范围/业务关系内。'],
    permissions: ['普通 view 权限不等于 SENSITIVE_VIEW；敏感 reveal 是更窄的动作权限。', '敏感权限也不能突破学院/班级/本人关系，更不能按姓名模糊匹配授权。'],
    steps: ['先判断当前页面显示脱敏值是否符合默认最小暴露设计。', '确需明文时通过正式 reveal 动作提交查看原因，由服务端再次校验权限、范围和稳定关系。', '确认成功查看写入安全审计；记录 traceId 便于追溯。', '若安全审计依赖不可用并返回 503/fail-closed，停止查看，不通过前端缓存、日志或数据库旁路获取明文。'],
    successCriteria: ['无敏感权限的人始终只看到脱敏/最小信息；合法 reveal 有原因、有审计、可追溯。'],
    troubleshooting: ['能看列表但看不到明文通常是正常安全边界。', '同名人员不能作为授权依据；应使用稳定 teacher_key/studentId/业务关系。'],
    nextSteps: ['敏感信息使用完成后回到普通业务流程，不复制到帮助文档、聊天记录或非授权导出。'],
    contactAdminWhen: ['满足敏感权限、范围、稳定业务关系和查看原因后仍无法 reveal。', '发现无审计、无查看原因或越范围即可获得敏感明文，应立即按 P0 安全缺陷处理。']
  }
]
