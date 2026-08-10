/** Help Center V3-05 · 高频故障库收口批：400 参数校验 + 404 数据不存在。 */
import { HELP_AUTHORIZATION_PRINCIPLE } from './helpRoleGuidance.js'

const COMMON_ROLES = ['学生', '任课教师', '辅导员', '学院管理员', '教务处管理员', '学工处管理员', '学校管理员']

export const HIGH_FREQUENCY_TROUBLESHOOTING_V305C_CARDS = [
  {
    id: 'tr-v3-validation-400',
    module: '高频故障库 · 参数与必填校验',
    title: '提示参数校验失败、必填项缺失或 400 时先按字段修正',
    roles: COMMON_ROLES,
    entry: '提交表单、审批意见、导入确认或其他写操作出现 VALIDATION_ERROR / 400 时',
    keywords: ['400', 'VALIDATION_ERROR', '参数校验失败', '必填', '字段错误', 'REJECT_REASON_REQUIRED', '校验失败'],
    summary: '统一异常处理会把请求参数校验失败转换为 VALIDATION_ERROR，并返回具体 field/msg；部分业务还会返回 REJECT_REASON_REQUIRED 等明确业务校验。400 通常表示当前请求本身不满足合同，不应靠重复点击解决。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['保留页面提示、错误 bizCode、field/msg 和 traceId。', '确认当前页面数据是服务器最新版本，避免拿旧表单继续提交。'],
    permissions: ['400 与 403 不同：参数修正不能替代 permissionCode、数据范围、业务关系和当前状态校验。'],
    steps: ['先看具体 bizCode 和字段错误，不只看“提交失败”。', '按 field/msg 修正必填、格式、长度、枚举值或业务要求的原因/备注。', '若是审批退回/驳回等动作，补齐服务端明确要求的 reason，不用空格或无意义文字绕过。', '修正后只重新提交一次；如果随后变成 409，按版本冲突卡刷新服务器真值。'],
    successCriteria: ['表单只在满足服务端字段和业务合同后提交成功；错误字段可定位，不产生重复写入。'],
    troubleshooting: ['页面显示已填写但仍提示缺失：检查是否填在正确字段、是否被前端清空或不在本动作 payload。', '所有字段看似正确仍 400：以服务端 field/msg 和当前业务状态为准，不猜隐藏字段。'],
    nextSteps: ['校验通过后继续当前业务；若错误转为 403/409，切换到对应故障卡排查。'],
    contactAdminWhen: ['服务端返回的 field/msg 与页面实际字段不一致，导致用户无法修正。', '同一合法请求稳定返回 400 且没有可解释字段或业务原因。']
  },
  {
    id: 'tr-v3-not-found-404',
    module: '高频故障库 · 数据与旧链接',
    title: '提示数据不存在 / 404：先从当前列表重新进入，不要手改链接或记录 ID',
    roles: COMMON_ROLES,
    entry: '打开详情、旧收藏、通知深链或任务链接时出现 DATA_NOT_FOUND / 404',
    keywords: ['404', 'DATA_NOT_FOUND', 'TENANT_NOT_FOUND', 'ROLE_NOT_FOUND', '数据不存在', '记录不存在', '旧链接', '收藏失效'],
    summary: '404 表示当前请求没有可返回的目标资源。它可能是记录已不存在、旧链接失效、租户/角色上下文变化，也可能是服务端为了避免泄露越范围对象而按“不可见即不存在”处理；因此不能通过猜测 ID、改 URL 或切换高权限账号探测数据。',
    authorizationPrinciple: HELP_AUTHORIZATION_PRINCIPLE,
    prerequisites: ['确认当前登录学校、角色和业务范围正确。', '保留原链接、业务对象线索和 traceId，不反复修改 URL 猜 ID。'],
    permissions: ['404 不等于自动拥有恢复/查看权限；越范围对象可能故意不暴露是否存在。'],
    steps: ['先回到当前模块正式列表或待办列表重新搜索目标记录。', '如果列表仍能看到目标，使用列表生成的最新详情入口重新打开。', '如果列表已看不到，确认业务是否已归档/删除、租户或角色是否变化，以及本人/学院/班级/导师等关系是否仍成立。', '旧收藏或通知链接失效时，以当前系统重新生成的 route/recordId 为准，不手工拼接路径。'],
    successCriteria: ['用户从当前真实列表进入正确记录，或明确确认该记录当前不可见/不存在；不会通过 URL 猜测泄露其他范围数据。'],
    troubleshooting: ['同一条记录别人能看、本人 404：先检查数据范围和业务关系，不要求对方复制详情 URL。', '旧书签 404 但系统有新入口：更新收藏即可，不把旧路径恢复成无条件兜底。'],
    nextSteps: ['找到当前记录后继续业务；确认记录不存在时按对应模块正式新建/恢复规则处理。'],
    contactAdminWhen: ['目标记录在本人当前列表中明确可见，但点击最新详情入口仍稳定 404。', '404 页面暴露了其他租户/学院对象是否存在等敏感信息，应按越权信息泄露处理。']
  }
]
